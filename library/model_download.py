from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from django.core.files import File
from django.db import transaction

from library.download_providers import get_download_provider
from library.download_providers.base import RemoteDownloadFile
from library.downloads import DownloadError, download_to_path, is_convertible_remote_filename
from library.mesh_convert import MeshConvertError, convert_mesh_to_stl
from library.models import ModelFile, ModelStatus, SavedModel

logger = logging.getLogger(__name__)

MAX_FILES_PER_MODEL = 20


def _queue_file_processing(file_id: int) -> None:
    try:
        from library.tasks import analyze_model_file

        analyze_model_file.delay(file_id)
    except Exception:
        try:
            analyze_model_file(file_id)
        except Exception:
            logger.exception("Failed to process downloaded model file %s", file_id)


@transaction.atomic
def _attach_downloaded_file(model: SavedModel, *, original_name: str, temp_path: Path) -> ModelFile:
    ext = Path(original_name).suffix.lower().lstrip(".") or "stl"
    with temp_path.open("rb") as handle:
        model_file = ModelFile.objects.create(
            model=model,
            file=File(handle, name=Path(original_name).name),
            file_type=ext,
            original_name=Path(original_name).name,
            file_size=temp_path.stat().st_size,
        )
    return model_file


def _prepare_downloaded_file(remote: RemoteDownloadFile, temp_path: Path) -> tuple[Path, str]:
    if not is_convertible_remote_filename(remote.name):
        return temp_path, remote.name

    stl_path = temp_path.with_suffix(".stl")
    try:
        convert_mesh_to_stl(temp_path, stl_path)
    except MeshConvertError as exc:
        temp_path.unlink(missing_ok=True)
        raise DownloadError(str(exc)) from exc
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)

    stl_name = Path(remote.name).with_suffix(".stl").name
    return stl_path, stl_name


def _download_remote_file_for_attach(remote: RemoteDownloadFile) -> tuple[Path, str]:
    suffix = Path(remote.name).suffix or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        temp_path = Path(tmp.name)
    download_to_path(remote.url, temp_path, headers=remote.headers)
    return _prepare_downloaded_file(remote, temp_path)


def download_files_for_model(model: SavedModel) -> dict:
    if model.files.exists():
        return {"status": "skipped", "reason": "files_already_present"}

    provider = get_download_provider(model)
    if not provider:
        return {
            "status": "unsupported",
            "error": f"Automatic download is not supported for {model.source_site or 'this site'}",
        }

    try:
        remote_files = provider.list_files(model)
    except DownloadError as exc:
        return {"status": "failed", "error": str(exc)}
    except Exception as exc:
        logger.warning("File list failed for model %s: %s", model.pk, exc)
        return {"status": "failed", "error": str(exc)}

    if not remote_files:
        return {"status": "failed", "error": "No downloadable mesh files found for this model"}

    downloaded: list[dict] = []
    errors: list[str] = []

    for remote in remote_files[:MAX_FILES_PER_MODEL]:
        temp_path: Path | None = None
        original_name = remote.name
        try:
            temp_path, original_name = _download_remote_file_for_attach(remote)
            model_file = _attach_downloaded_file(model, original_name=original_name, temp_path=temp_path)
            _queue_file_processing(model_file.id)
            downloaded.append({"id": model_file.id, "name": model_file.original_name, "size": model_file.file_size})
        except (DownloadError, OSError) as exc:
            errors.append(f"{remote.name}: {exc}")
            logger.warning("Failed to download %s for model %s: %s", remote.name, model.pk, exc)
        finally:
            if temp_path and temp_path.exists():
                temp_path.unlink(missing_ok=True)

    if not downloaded:
        return {"status": "failed", "error": "; ".join(errors) or "download failed"}

    model.status = ModelStatus.DOWNLOADED
    meta = model.metadata or {}
    meta["download_status"] = "complete"
    meta.pop("download_error", None)
    meta["downloaded_files"] = downloaded
    if errors:
        meta["download_warnings"] = errors
    model.metadata = meta
    model.save(update_fields=["status", "metadata", "updated_at"])
    return {"status": "complete", "files": downloaded, "warnings": errors}
