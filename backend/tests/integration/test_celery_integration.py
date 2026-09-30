import pytest

from backend.src.celery_app import celery_app


class TestCeleryIntegration:
    """Integration tests for Celery configuration (Phase C.2)."""

    def test_celery_app_has_correct_broker(self):
        """Verify Celery broker URL matches config."""
        from backend.src.config import get_settings
        settings = get_settings()
        assert settings.CELERY_BROKER_URL in celery_app.conf.broker_url

    def test_process_message_task_signature(self):
        """Verify process_message task accepts expected arguments."""
        from backend.src.tasks.message_tasks import process_message
        # Task should accept: user_id, message, channel_type
        assert process_message.name == "backend.src.tasks.message_tasks.process_message"

    def test_extract_facts_task_signature(self):
        """Verify extract_facts task exists and is registered."""
        from backend.src.tasks.fact_tasks import extract_facts
        assert extract_facts.name == "backend.src.tasks.fact_tasks.extract_facts"

    def test_beat_schedule_has_decay_task(self):
        """Verify decay agent is in beat schedule."""
        schedule = celery_app.conf.beat_schedule
        assert "decay-agent-hourly" in schedule
        task = schedule["decay-agent-hourly"]
        # Celery stores numeric schedules as-is (float) in beat_schedule
        assert task["schedule"] == 3600.0  # seconds
