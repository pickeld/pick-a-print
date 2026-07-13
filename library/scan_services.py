from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.db import transaction

from app.models.enums import JobStage, PIPELINE_STAGES
from app.models.progress import STAGE_HINTS, stale_after_seconds
from app.pipeline.input_extract import ARCHIVE_EXTENSIONS, MEDIA_EXTENSIONS
from app.models.job import Job as PipelineJob
from app.pipeline.glb_export import ensure_glb_from_ply, is_valid_glb
from app.pipeline.preview import (
    build_preview_warnings,
    count_frames,
    is_placeholder_mesh,
)
from app.pipeline.hardware import colmap_cuda_available
from app.pipeline.stages import STAGE_DESCRIPTIONS
from app.pipeline.workspace import JobWorkspace
from app.storage.local import LocalStorage
from app.storage.minio_storage import MinioStorage, get_storage
from library.models import ScanJob
from library.services import ModelSaveError, save_model_from_upload


class ScanError(Exception):
    pass


def workspace_root() -> Path:
    return Path(os.getenv("PIPELINE_DATA_DIR", str(settings.PIPELINE_DATA_DIR)))


def get_pipeline_steps() -> list[dict[str, str]]:
    steps = []
    for stage in PIPELINE_STAGES:
        if stage == JobStage.COMPLETED:
            continue
        steps.append(
            {
                "key": stage.value,
                "label": STAGE_DESCRIPTIONS.get(stage, stage.value.replace("_", " ").title()),
            }
        )
    return steps


def _step_index(stage_value: str) -> int:
    try:
        return next(i for i, s in enumerate(PIPELINE_STAGES) if s.value == stage_value)
    except StopIteration:
        return 0


def step_state(step_key: str, current_stage: str, failed: bool, failed_stage: str | None = None) -> str:
    """Return pending | active | done | failed for a pipeline step."""
    if failed:
        fail_at = failed_stage or current_stage
        if step_key == fail_at:
            return "failed"
        fail_idx = _step_index(fail_at) if fail_at != "FAILED" else _step_index(step_key)
        step_idx = _step_index(step_key)
        if fail_at != "FAILED" and step_idx < fail_idx:
            return "done"
        if fail_at != "FAILED" and step_idx > fail_idx:
            return "pending"
        return "pending"

    current_idx = _step_index(current_stage)
    step_idx = _step_index(step_key)
    if current_stage == "COMPLETED":
        return "done"
    if step_idx < current_idx:
        return "done"
    if step_idx == current_idx:
        return "active"
    return "pending"


def load_pipeline_job(job_id: str) -> PipelineJob:
    return PipelineJob.load(workspace_root(), job_id)


def sync_scan_job(scan_job: ScanJob) -> ScanJob:
    """Refresh Django record from on-disk pipeline job.json."""
    root = workspace_root()
    storage = get_storage()
    if isinstance(storage, MinioStorage):
        storage.pull_job_state(str(scan_job.job_id), root / str(scan_job.job_id))
    pipeline_job = load_pipeline_job(str(scan_job.job_id))
    stage = pipeline_job.stage.value if isinstance(pipeline_job.stage, JobStage) else str(pipeline_job.stage)
    scan_job.stage = stage
    scan_job.progress = pipeline_job.progress
    scan_job.error = pipeline_job.error or ""
    scan_job.save(update_fields=["stage", "progress", "error", "updated_at"])
    return scan_job


def queue_scan(job_id: str) -> None:
    """Publish to the scan Celery broker (redis db 1), not Django's library broker (db 0)."""
    import os

    try:
        from kombu import Connection

        from app.workers.tasks import run_scan

        broker = os.getenv("SCAN_CELERY_BROKER_URL", "redis://localhost:6379/1")
        with Connection(broker) as conn:
            run_scan.apply_async(args=[job_id], connection=conn)
    except Exception as exc:
        raise ScanError(f"Could not queue scan job. Is the scan worker running? ({exc})") from exc


def _validate_upload_files(files) -> None:
    allowed = MEDIA_EXTENSIONS | ARCHIVE_EXTENSIONS
    for uploaded in files:
        ext = Path(uploaded.name).suffix.lower()
        if ext not in allowed:
            raise ScanError(
                f"Unsupported file type: {uploaded.name}. "
                "Upload photos, video, or a .zip archive."
            )


@transaction.atomic
def create_scan_job(
    *,
    user,
    files,
    title: str | None = None,
    tag_names: list[str] | None = None,
    collection_ids: list[int] | None = None,
) -> ScanJob:
    if not files:
        raise ScanError("Upload at least one photo, video, or .zip archive.")

    from library.scan_worker import assert_scan_worker_ready

    assert_scan_worker_ready()

    _validate_upload_files(files)

    max_bytes = settings.SCAN_MAX_UPLOAD_MB * 1024 * 1024
    total_size = sum(getattr(f, "size", 0) or 0 for f in files)
    if total_size > max_bytes:
        raise ScanError(f"Total upload exceeds {settings.SCAN_MAX_UPLOAD_MB} MB limit.")

    job_id = str(uuid.uuid4())
    root = workspace_root()
    storage = LocalStorage(root)
    ws = storage.workspace(job_id)
    ws.ensure_dirs()

    for uploaded in files:
        dest = ws.input_dir / uploaded.name
        with dest.open("wb") as out:
            for chunk in uploaded.chunks():
                out.write(chunk)

    display_title = title or f"Scan {job_id[:8]}"
    pipeline_job = PipelineJob.create(job_id)
    pipeline_job.metadata = {
        "user_id": user.id,
        "title": display_title,
        "file_count": len(files),
    }
    has_zip = any(Path(f.name).suffix.lower() in ARCHIVE_EXTENSIONS for f in files)
    pipeline_job.append_log(
        f"Received {len(files)} upload(s)"
        + (" including zip archive(s)" if has_zip else ""),
        JobStage.UPLOADED,
    )
    pipeline_job.save(root)

    scan_job = ScanJob.objects.create(
        user=user,
        job_id=job_id,
        title=display_title,
        stage=JobStage.UPLOADED.value,
        input_file_count=len(files),
        metadata={
            "tag_names": tag_names or [],
            "collection_ids": collection_ids or [],
        },
    )

    storage = get_storage()
    if isinstance(storage, MinioStorage):
        try:
            storage.upload_workspace(job_id, ws.root)
        except Exception as exc:
            raise ScanError(f"Could not upload scan inputs for remote worker: {exc}") from exc

    queue_scan(job_id)
    return scan_job


def get_scan_outputs(scan_job: ScanJob) -> dict[str, Path]:
    ws = JobWorkspace(workspace_root(), str(scan_job.job_id))
    outputs: dict[str, Path] = {}
    mapping = {
        "stl": ws.output_stl(),
        "glb": ws.output_glb(),
        "ply": ws.output_ply(),
        "obj": ws.output_obj(),
        "report": ws.output_report(),
    }
    for key, path in mapping.items():
        if path.exists():
            outputs[key] = path

    # Repair invalid GLB files from older runs / stale workers.
    ply = outputs.get("ply")
    glb = outputs.get("glb")
    if ply and (not glb or not is_valid_glb(glb)):
        try:
            glb_path = ensure_glb_from_ply(ply, ws.output_glb(), ws.output_obj())
            outputs["glb"] = glb_path
            if ws.output_obj().exists():
                outputs["obj"] = ws.output_obj()
        except Exception:
            pass

    return outputs


def _load_report(ws: JobWorkspace) -> dict:
    report_path = ws.output_report()
    if not report_path.exists():
        return {}
    try:
        import json

        return json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _preview_status(scan_job: ScanJob, output_paths: dict[str, Path]) -> dict:
    ws = JobWorkspace(workspace_root(), str(scan_job.job_id))
    report = _load_report(ws)
    pipeline_job = load_pipeline_job(str(scan_job.job_id))
    frame_count = int(
        report.get("frame_count")
        or pipeline_job.metadata.get("frame_count")
        or count_frames(ws.frames_dir)
    )
    gpu_available = bool(
        report.get("gpu_available", pipeline_job.metadata.get("gpu_available", colmap_cuda_available()))
    )
    ply = output_paths.get("ply")
    placeholder = bool(report.get("placeholder_mesh")) or (
        bool(ply) and is_placeholder_mesh(ply)
    )
    warnings = report.get("warnings")
    if not warnings:
        warnings = build_preview_warnings(
            frame_count=frame_count,
            placeholder_mesh=placeholder,
            gpu_available=gpu_available,
        )
    return {
        "gpu_available": gpu_available,
        "frame_count": frame_count,
        "placeholder_mesh": placeholder,
        "warnings": warnings,
    }


def _parse_utc_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _worker_status(stage: str, *, completed: bool, failed: bool, seconds_since_update: int | None) -> str:
    if completed:
        return "completed"
    if failed:
        return "failed"
    if stage == JobStage.UPLOADED.value and (seconds_since_update is None or seconds_since_update > 30):
        return "queued"
    if seconds_since_update is None:
        return "active"
    try:
        stale_after = stale_after_seconds(JobStage(stage))
    except ValueError:
        stale_after = 900
    if seconds_since_update > stale_after:
        return "possibly_stalled"
    return "active"


def _latest_activity(pipeline_job) -> str | None:
    if pipeline_job.log_lines:
        return pipeline_job.log_lines[-1]
    stage = pipeline_job.stage.value if isinstance(pipeline_job.stage, JobStage) else str(pipeline_job.stage)
    return pipeline_job.stage_logs.get(stage) or None


def build_status_payload(scan_job: ScanJob) -> dict:
    scan_job = sync_scan_job(scan_job)
    pipeline_job = load_pipeline_job(str(scan_job.job_id))
    steps = get_pipeline_steps()
    failed = scan_job.stage == JobStage.FAILED.value
    failed_stage = None
    if failed and scan_job.error and ":" in scan_job.error:
        failed_stage = scan_job.error.split(":", 1)[0].strip()
    for step in steps:
        step["state"] = step_state(step["key"], scan_job.stage, failed, failed_stage)

    outputs = {}
    viewer_url = None
    preview = {
        "gpu_available": colmap_cuda_available(),
        "frame_count": count_frames(JobWorkspace(workspace_root(), str(scan_job.job_id)).frames_dir),
        "placeholder_mesh": False,
        "warnings": [],
    }
    if scan_job.is_completed:
        output_paths = get_scan_outputs(scan_job)
        for key, path in output_paths.items():
            outputs[key] = path.name
        if "glb" in outputs:
            viewer_url = outputs["glb"]
        preview = _preview_status(scan_job, output_paths)

    stage_value = scan_job.stage
    try:
        stage_enum = JobStage(stage_value)
        stage_label = STAGE_DESCRIPTIONS.get(stage_enum, stage_value.replace("_", " ").title())
        stage_hint = STAGE_HINTS.get(stage_enum)
    except ValueError:
        stage_label = stage_value.replace("_", " ").title()
        stage_hint = None

    updated_at = pipeline_job.updated_at
    updated_dt = _parse_utc_timestamp(updated_at)
    seconds_since_update = None
    if updated_dt is not None:
        seconds_since_update = max(0, int((datetime.now(timezone.utc) - updated_dt).total_seconds()))

    worker_status = _worker_status(
        stage_value,
        completed=scan_job.is_completed,
        failed=failed,
        seconds_since_update=seconds_since_update,
    )

    return {
        "job_id": str(scan_job.job_id),
        "title": scan_job.title,
        "stage": scan_job.stage,
        "stage_label": stage_label,
        "stage_hint": stage_hint,
        "progress": scan_job.progress,
        "error": scan_job.error or None,
        "updated_at": updated_at,
        "seconds_since_update": seconds_since_update,
        "worker_status": worker_status,
        "activity": _latest_activity(pipeline_job),
        "log_lines": pipeline_job.log_lines,
        "stage_logs": pipeline_job.stage_logs,
        "steps": steps,
        "completed": scan_job.is_completed,
        "failed": failed,
        "outputs": outputs,
        "viewer_file": viewer_url,
        "saved_model_id": scan_job.saved_model_id,
        "preview": preview,
    }


@transaction.atomic
def import_scan_to_library(scan_job: ScanJob) -> ScanJob:
    if scan_job.saved_model_id:
        return scan_job
    if not scan_job.is_completed:
        raise ScanError("Scan is not completed yet.")

    outputs = get_scan_outputs(scan_job)
    stl_path = outputs.get("stl")
    if not stl_path:
        raise ScanError("STL output not found.")

    meta = scan_job.metadata or {}
    tag_names = meta.get("tag_names") or []
    collection_ids = meta.get("collection_ids") or []

    with stl_path.open("rb") as handle:
        django_file = File(handle, name=stl_path.name)
        try:
            model = save_model_from_upload(
                user=scan_job.user,
                uploaded_file=django_file,
                title=scan_job.title,
                tag_names=tag_names or None,
                collection_ids=collection_ids or None,
            )
        except ModelSaveError as exc:
            raise ScanError(str(exc)) from exc

    model.source_site = "scan"
    model.metadata = {
        **(model.metadata or {}),
        "scan_job_id": str(scan_job.job_id),
        "fetch_status": "scan",
    }
    model.save(update_fields=["source_site", "metadata"])

    model_file = model.files.first()
    glb_source = outputs.get("glb")
    if model_file and glb_source:
        from library.stl_preview import copy_preview_glb

        copy_preview_glb(glb_source, Path(model_file.file.path))

    scan_job.saved_model = model
    scan_job.save(update_fields=["saved_model", "updated_at"])
    return scan_job
