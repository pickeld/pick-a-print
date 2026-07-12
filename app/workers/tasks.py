from __future__ import annotations

import logging

from app.pipeline.config import PipelineConfig
from app.pipeline.orchestrator import process_scan
from app.storage import get_storage
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=2)
def run_scan(self, job_id: str) -> dict:
    """Celery task: run full reconstruction pipeline for a job."""
    config = PipelineConfig.from_env()

    storage = get_storage()
    ws = storage.workspace(job_id)
    if hasattr(storage, "download_prefix"):
        storage.download_prefix(job_id, ws.root)

    def checkpoint(_job) -> None:
        if hasattr(storage, "push_job_state"):
            storage.push_job_state(job_id, ws.root)

    job = process_scan(job_id, config, on_checkpoint=checkpoint)

    if hasattr(storage, "push_job_state"):
        storage.push_job_state(job_id, ws.root)
    elif hasattr(storage, "sync_outputs") and ws.output_dir.exists():
        storage.sync_outputs(job_id, ws.output_dir)

    return job.to_dict()


@celery_app.task(bind=True)
def run_stage(self, job_id: str, stage: str) -> dict:
    """Re-run pipeline from a specific stage."""
    from app.models.enums import JobStage
    from app.pipeline.orchestrator import ReconstructionPipeline

    config = PipelineConfig.from_env()
    storage = get_storage()
    ws = storage.workspace(job_id)
    if hasattr(storage, "download_prefix"):
        storage.download_prefix(job_id, ws.root)

    pipeline = ReconstructionPipeline(job_id, config)

    def checkpoint(_job) -> None:
        if hasattr(storage, "push_job_state"):
            storage.push_job_state(job_id, ws.root)

    pipeline._on_checkpoint = checkpoint
    job = pipeline.run(from_stage=JobStage(stage))

    if hasattr(storage, "push_job_state"):
        storage.push_job_state(job_id, ws.root)
    elif hasattr(storage, "sync_outputs") and ws.output_dir.exists():
        storage.sync_outputs(job_id, ws.output_dir)

    return job.to_dict()
