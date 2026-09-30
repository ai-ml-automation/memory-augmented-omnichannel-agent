"""
Unit Tests for Celery App and registered tasks

Verifies app configuration and that tasks are registered and
discoverable via the Celery app.
"""

import pytest

# Ensure all task modules are imported so @celery_app.task decorators
# register them before we inspect celery_app.tasks.
import backend.src.tasks.message_tasks  # noqa: F401
import backend.src.tasks.fact_tasks  # noqa: F401
import backend.src.tasks.decay_tasks  # noqa: F401

from backend.src.celery_app import celery_app


# ---------------------------------------------------------------------------
# Celery app configuration
# ---------------------------------------------------------------------------


class TestCeleryAppConfig:
    """Tests for Celery application configuration."""

    def test_celery_app_broker_url(self):
        """Broker URL comes from settings.CELERY_BROKER_URL."""
        assert "redis" in celery_app.conf.broker_url

    def test_celery_app_result_backend(self):
        """Result backend comes from settings.CELERY_RESULT_BACKEND."""
        assert "redis" in celery_app.conf.result_backend

    def test_celery_app_serialization(self):
        """Task and result serializers are JSON."""
        assert celery_app.conf.task_serializer == "json"
        assert celery_app.conf.result_serializer == "json"
        assert celery_app.conf.accept_content == ["json"]

    def test_celery_app_timezone(self):
        """Timezone is UTC with UTC enabled."""
        assert celery_app.conf.timezone == "UTC"
        assert celery_app.conf.enable_utc is True

    def test_celery_app_task_config(self):
        """Track-started, acks-late, and prefetch settings are correct."""
        assert celery_app.conf.task_track_started is True
        assert celery_app.conf.task_acks_late is True
        assert celery_app.conf.worker_prefetch_multiplier == 1

    def test_celery_app_beat_schedule(self):
        """Beat schedule contains the decay-agent-hourly entry."""
        beat = celery_app.conf.beat_schedule
        assert "decay-agent-hourly" in beat

        decay_task = beat["decay-agent-hourly"]
        assert (
            decay_task["task"]
            == "backend.src.tasks.decay_tasks.run_decay_agent"
        )
        assert decay_task["schedule"] == 3600.0


# ---------------------------------------------------------------------------
# Registered tasks
# ---------------------------------------------------------------------------


class TestRegisteredTasks:
    """Tests that Celery tasks are registered and discoverable."""

    def test_process_message_task_exists(self):
        """process_message task is registered in the Celery app."""
        task_name = "backend.src.tasks.message_tasks.process_message"
        registered = celery_app.tasks
        assert task_name in registered, (
            f"Task '{task_name}' not found. Registered: {list(registered.keys())}"
        )

    def test_extract_facts_task_exists(self):
        """extract_facts task is registered in the Celery app."""
        task_name = "backend.src.tasks.fact_tasks.extract_facts"
        registered = celery_app.tasks
        assert task_name in registered, (
            f"Task '{task_name}' not found. Registered: {list(registered.keys())}"
        )

    def test_run_decay_agent_task_exists(self):
        """run_decay_agent task is registered in the Celery app."""
        task_name = "backend.src.tasks.decay_tasks.run_decay_agent"
        registered = celery_app.tasks
        assert task_name in registered, (
            f"Task '{task_name}' not found. Registered: {list(registered.keys())}"
        )
