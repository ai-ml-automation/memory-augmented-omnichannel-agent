"""
Настройка Celery для асинхронных фоновых задач.

Брокер/бэкенд — Redis (URL из Settings); JSON-сериализация задач;
task_acks_late + worker_prefetch_multiplier=1 дают at-least-once (задача
не теряется при падении воркера). beat_schedule каждый час запускает
агента затухания памяти (decay-agent-hourly → run_decay_agent).
"""

from celery import Celery

from backend.src.config import get_settings

settings = get_settings()

celery_app = Celery(
    "omnichannel",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "decay-agent-hourly": {
            "task": "backend.src.tasks.decay_tasks.run_decay_agent",
            "schedule": 3600.0,
        },
    },
)

celery_app.autodiscover_tasks(["backend.src.tasks"])
