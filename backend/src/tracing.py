"""
OpenTelemetry tracing configuration (Phase F.2.2).

Distributed tracing across the full pipeline with Jaeger export.
"""

import os

from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def setup_tracing(service_name: str = "omnichannel-backend") -> None:
    """
    Configure OpenTelemetry tracing with Jaeger export.

    Args:
        service_name: Service name for traces
    """
    # Jaeger endpoint from environment
    jaeger_host = os.getenv("JAEGER_HOST", "jaeger")
    jaeger_port = int(os.getenv("JAEGER_PORT", "6831"))

    # Resource with service info
    resource = Resource.create({
        SERVICE_NAME: service_name,
        "deployment.environment": os.getenv("APP_ENV", "development"),
    })

    # Tracer provider
    provider = TracerProvider(resource=resource)

    # Jaeger exporter
    jaeger_exporter = JaegerExporter(
        agent_host_name=jaeger_host,
        agent_port=jaeger_port,
    )

    # Batch span processor
    provider.add_span_processor(
        BatchSpanProcessor(jaeger_exporter)
    )

    # Set global provider
    trace.set_tracer_provider(provider)


def get_tracer(name: str) -> trace.Tracer:
    """
    Get a tracer instance.

    Args:
        name: Tracer name (usually module name)

    Returns:
        Tracer instance
    """
    return trace.get_tracer(name)
