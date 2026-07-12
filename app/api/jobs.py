from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.models.enums import JobStage
from app.models.job import Job
from app.pipeline.config import PipelineConfig
from app.storage import get_storage
from app.workers.tasks import run_scan, run_stage

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobCreateResponse(BaseModel):
    job_id: str
    stage: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    stage: str
    progress: float
    error: str | None
    created_at: str
    updated_at: str


@router.post("/", response_model=JobCreateResponse)
async def create_job(files: list[UploadFile] = File(...)) -> JobCreateResponse:
    if not files:
        raise HTTPException(400, "At least one file required")

    job_id = str(uuid.uuid4())
    storage = get_storage()
    ws = storage.workspace(job_id)
    ws.ensure_dirs()

    for upload in files:
        dest = ws.input_dir / upload.filename
        with dest.open("wb") as f:
            shutil.copyfileobj(upload.file, f)

    job = Job.create(job_id)
    job.save(storage.root)

    run_scan.delay(job_id)
    return JobCreateResponse(job_id=job_id, stage=job.stage.value, message="Job queued")


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: str) -> JobStatusResponse:
    storage = get_storage()
    job = Job.load(storage.root, job_id)
    if not (storage.root / job_id).exists():
        raise HTTPException(404, "Job not found")
    return JobStatusResponse(
        job_id=job.id,
        stage=job.stage.value,
        progress=job.progress,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.post("/{job_id}/retry")
async def retry_job(job_id: str, from_stage: JobStage | None = None) -> dict:
    storage = get_storage()
    if not (storage.root / job_id).exists():
        raise HTTPException(404, "Job not found")
    if from_stage:
        task = run_stage.delay(job_id, from_stage.value)
    else:
        task = run_scan.delay(job_id)
    return {"job_id": job_id, "task_id": task.id}


@router.get("/{job_id}/outputs")
async def list_outputs(job_id: str) -> dict:
    storage = get_storage()
    ws = storage.workspace(job_id)
    if not ws.root.exists():
        raise HTTPException(404, "Job not found")
    outputs = {}
    if ws.output_dir.exists():
        for f in ws.output_dir.iterdir():
            if f.is_file():
                outputs[f.name] = str(f)
    return {"job_id": job_id, "outputs": outputs}
