"""
Celery integration tests (Phase C.2).

Проверяют конфигурацию Celery, а не бизнес-логику задач:
брокер берётся из настроек, задачи зарегистрированы под ожидаемыми
именами, beat-расписание содержит decay-задачу. Ловит регрессии
конфига (смену брокера/имён задач/периода) без реального брокера.
"""

import pytest

from backend.src.celery_app import celery_app


class TestCeleryIntegration:
    """Группа тестов конфигурации Celery: брокер, имена задач, beat.

    Покрывают слой интеграции приложение ↔ Celery: проверяют, что
    конфиг из настроек доехал до приложения, задачи зарегистрированы
    под ожидаемыми полными именами, decay-задача есть в расписании.
    """

    def test_celery_app_has_correct_broker(self):
        """Ловит рассинхрон: брокер Celery отвязан от CELERY_BROKER_URL.

        Берём актуальный URL из get_settings() и проверяем, что он
        присутствует в настроенном broker_url приложения.
        """
        from backend.src.config import get_settings
        settings = get_settings()
        assert settings.CELERY_BROKER_URL in celery_app.conf.broker_url

    def test_process_message_task_signature(self):
        """Ловит переименование/перемещение задачи process_message.

        Задача должна быть зарегистрирована под полным путём
        backend.src.tasks.message_tasks.process_message, иначе
        воркер не найдёт её по имени.
        """
        from backend.src.tasks.message_tasks import process_message
        # Task should accept: user_id, message, channel_type
        assert process_message.name == "backend.src.tasks.message_tasks.process_message"

    def test_extract_facts_task_signature(self):
        """Ловит переименование/перемещение задачи extract_facts.

        Аналогично process_message: имя задачи — часть контракта
        между приложением и Celery-воркером.
        """
        from backend.src.tasks.fact_tasks import extract_facts
        assert extract_facts.name == "backend.src.tasks.fact_tasks.extract_facts"

    def test_beat_schedule_has_decay_task(self):
        """Ловит удаление/переименование decay-задачи из beat-расписания.

        Периодический запуск decay-агента (затухание фактов) —
        требование III.1; без него забытые факты никогда не затухают.
        """
        schedule = celery_app.conf.beat_schedule
        assert "decay-agent-hourly" in schedule
        task = schedule["decay-agent-hourly"]
        # Celery stores numeric schedules as-is (float) in beat_schedule
        assert task["schedule"] == 3600.0  # seconds
