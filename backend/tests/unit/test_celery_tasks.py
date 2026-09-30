"""
Unit Tests for Celery App and registered tasks

Проверяют конфигурацию celery_app и то, что все задачи зарегистрированы
и обнаруживаются через celery_app.tasks.

Зачем эти тесты: битая конфигурация Celery (брокер, сериализация,
retry-политика) проявляется только в проде; структурные тесты ловят её
на этапе юнитов. Отдельно проверяется, что декораторы @celery_app.task
в реально сработали — иначе задачи молча не выполняются воркером.
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
    """Группа структурных тестов конфигурации celery_app.

    Проверяют брокер и result backend на Redis, JSON-сериализацию,
    UTC-таймзону, надёжную доставку (acks_late, track_started)
    и расписание beat для decay-агента.
    """

    def test_celery_app_broker_url(self):
        """Ловит баг, если брокер не на Redis.

        broker_url обязан содержать "redis" — брокер из settings.
        Опечатка в URL или неверный транспорт остановят доставку
        задач ещё до запуска воркера.
        """
        assert "redis" in celery_app.conf.broker_url

    def test_celery_app_result_backend(self):
        """Ловит баг, если result backend не на Redis.

        result_backend обязан содержать "redis" — иначе результаты задач
        не будут доступны (polling статусов, retry-логика).
        """
        assert "redis" in celery_app.conf.result_backend

    def test_celery_app_serialization(self):
        """Ловит баг, если сериализация задач не JSON.

        task_serializer, result_serializer и accept_content обязаны быть
        "json". Пикл-сериализация — риск выполнения произвольного кода
        при приёме задач из ненадёжного источника.
        """
        assert celery_app.conf.task_serializer == "json"
        assert celery_app.conf.result_serializer == "json"
        assert celery_app.conf.accept_content == ["json"]

    def test_celery_app_timezone(self):
        """Ловит баг, если таймзона Celery не UTC.

        timezone обязан быть "UTC" с включённым enable_utc — иначе
        планировщик beat и метки времени задач разъедутся с остальной
        системой (все хронологии хранятся в UTC).
        """
        assert celery_app.conf.timezone == "UTC"
        assert celery_app.conf.enable_utc is True

    def test_celery_app_task_config(self):
        """Ловит баг, если надёжность доставки задач отключена.

        task_track_started=True, task_acks_late=True и prefetch_multiplier=1
        гарантируют: воркер не теряет задачу при падении и не берёт
        лишние задачи в буфер. Их отключение — потерянные сообщения.
        """
        assert celery_app.conf.task_track_started is True
        assert celery_app.conf.task_acks_late is True
        assert celery_app.conf.worker_prefetch_multiplier == 1

    def test_celery_app_beat_schedule(self):
        """Ловит баг, если decay-агент не в расписании beat.

        В beat_schedule обязан быть "decay-agent-hourly", указывающий
        на run_decay_agent с интервалом 3600 с. Пропуск расписания
        остановит периодическое затухание старых фактов.
        """
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
    """Группа тестов регистрации задач в celery_app.

    Проверяют, что декораторы @celery_app.task реально сработали
    и имена задач (module.function) видимы через celery_app.tasks.
    """

    def test_process_message_task_exists(self):
        """Ловит баг, если process_message не зарегистрирована в Celery.

        Имя задачи обязано присутствовать в celery_app.tasks — иначе
        воркер не найдёт её по имени при отложенной отправке.
        """
        task_name = "backend.src.tasks.message_tasks.process_message"
        registered = celery_app.tasks
        assert task_name in registered, (
            f"Task '{task_name}' not found. Registered: {list(registered.keys())}"
        )

    def test_extract_facts_task_exists(self):
        """Ловит баг, если extract_facts не зарегистрирована в Celery.

        Имя задачи обязано присутствовать в celery_app.tasks — фоновое
        извлечение фактов из сообщений станет мёртвой ссылкой.
        """
        task_name = "backend.src.tasks.fact_tasks.extract_facts"
        registered = celery_app.tasks
        assert task_name in registered, (
            f"Task '{task_name}' not found. Registered: {list(registered.keys())}"
        )

    def test_run_decay_agent_task_exists(self):
        """Ловит баг, если run_decay_agent не зарегистрирована в Celery.

        Имя задачи обязано присутствовать в celery_app.tasks — иначе
        запись beat "decay-agent-hourly" будет указывать на несуществующую
        задачу и затухание фактов молча прекратится.
        """
        task_name = "backend.src.tasks.decay_tasks.run_decay_agent"
        registered = celery_app.tasks
        assert task_name in registered, (
            f"Task '{task_name}' not found. Registered: {list(registered.keys())}"
        )
