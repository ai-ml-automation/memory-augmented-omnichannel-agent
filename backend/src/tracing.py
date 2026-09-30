"""
Конфигурация распределённой трассировки OpenTelemetry (Phase F.2.2).

Настраивает глобальный TracerProvider и экспорт спанов в Jaeger через
UDP-агент (порт 6831): каждый сервис шлёт спаны, Jaeger собирает их
в единый трейс по всему пайплайну (вебхук → Celery → LLM → ответ).

Спаны создаются не здесь, а инструментируемыми библиотеками
(FastAPI, SQLAlchemy) через `get_tracer`. PII не маскируется на уровне
трейсинга — маскирование выполняется в `logging_config.py` (фильтры),
атрибуты спанов не содержат персональных данных.
"""

import os

from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def setup_tracing(service_name: str = "omnichannel-backend") -> None:
    """
    Настройка глобального трейс-провайдера с экспортом в Jaeger.

    Создаёт Resource (service.name, deployment.environment) и вешает
    `BatchSpanProcessor`: спаны буферизуются и отправляются пачками.

    Args:
        service_name: имя сервиса для идентификации трейсов
    """
    # Хост/порт Jaeger-агента из окружения (для docker-compose)
    jaeger_host = os.getenv("JAEGER_HOST", "jaeger")
    jaeger_port = int(os.getenv("JAEGER_PORT", "6831"))

    # Ресурс описывает сервис и окружение
    resource = Resource.create({
        SERVICE_NAME: service_name,
        "deployment.environment": os.getenv("APP_ENV", "development"),
    })

    # Провайдер трейсов (глобальный для приложения)
    provider = TracerProvider(resource=resource)

    # Экспортёр: UDP-агент Jaeger
    jaeger_exporter = JaegerExporter(
        agent_host_name=jaeger_host,
        agent_port=jaeger_port,
    )

    # Буферизованная отправка спанов пачками
    provider.add_span_processor(
        BatchSpanProcessor(jaeger_exporter)
    )

    # Делаем провайдер глобальным — trace.get_tracer() использует его
    trace.set_tracer_provider(provider)


def get_tracer(name: str) -> trace.Tracer:
    """
    Получение трейсера для именованной инструментации (обычно имя
    модуля — группирует спаны по компонентам в Jaeger).

    Args:
        name: имя трейсера (обычно имя модуля)
    Returns:
        Tracer: экземпляр для создания спанов
    """
    return trace.get_tracer(name)
