import os

from celery import Celery

broker = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
backend = os.getenv("CELERY_RESULT_BACKEND", broker)

celery_app = Celery("photogrammetry", broker=broker, backend=backend)
celery_app.conf.update(
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
