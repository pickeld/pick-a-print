import os

from celery import Celery

# Use explicit conf keys — Celery auto-reads CELERY_BROKER_URL from the environment,
# which would route scan tasks to the Django library worker (redis db 0) instead of db 1.
_scan_broker = os.getenv("SCAN_CELERY_BROKER_URL", "redis://localhost:6379/1")
_scan_backend = os.getenv("SCAN_CELERY_RESULT_BACKEND", _scan_broker)

celery_app = Celery("photogrammetry")
celery_app.conf.update(
    broker_url=_scan_broker,
    result_backend=_scan_backend,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=3600 * 12,
    task_soft_time_limit=3600 * 11,
)

# Import tasks so Celery registers them
import app.workers.tasks  # noqa: F401, E402
