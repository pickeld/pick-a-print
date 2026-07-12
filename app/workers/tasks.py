from __future__ import annotations

import logging

from app.pipeline.config import PipelineConfig
from app.pipeline.orchestrator import ReconstructionPipeline, process_scan
from app.storage import get_storage
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=2)
def run_scan(self, job_id: str, mock: bool = False) -> dict:
    """Celery task: run full reconstruction pipeline for a job."""
    config = PipelineConfig.from_env()
    config.mock = mock or config.mock

    storage = get_storage()
    if hasattr(storage, "download_prefix"):
        storage.download_prefix(job_id, storage.root / job_id)

    job = process_scan(job_id, config)

    ws = storage.workspace(job_id)
    if hasattr(storage, "sync_outputs") and ws.output_dir.exists():
        storage.sync_outputs(job_id, ws.output_dir)

    return job.to_dict()


@celery_app.task(bind=True)
def run_stage(self, job_id: str, stage: str, mock: bool = False) -> dict:
    """Re-run pipeline from a specific stage."""
    from app.models.enums import JobStage

    config = PipelineConfig.from_env()
    config.mock = mock or config.mock
    pipeline = ReconstructionPipeline(job_id, config)
    job = pipeline.run(from_stage=JobStage(stage))
    return job.to_dict()
