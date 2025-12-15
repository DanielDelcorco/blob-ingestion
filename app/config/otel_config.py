import atexit
import os
import logging

from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader


def setup_otel(logger=None):
    """Configure OpenTelemetry tracing and metrics providers.

    Uses `OTEL_EXPORTER_OTLP_ENDPOINT` from environment or defaults to
    `http://localhost:4317`. Registers a shutdown handler with `atexit`
    that flushes exporters on process exit.

    Returns a tuple `(tracer_provider, meter_provider, shutdown_otel)` so callers can
    optionally perform explicit shutdown if their runtime provides a
    lifecycle hook.
    """
    if logger is None:
        logger = logging.getLogger("blob_ingestion")

    # If no endpoint configured, skip creating exporters (useful for tests/local)
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")

    headers_env = os.getenv("OTEL_EXPORTER_OTLP_HEADERS")
    headers = {}
    if headers_env:
        for pair in headers_env.split(","):
            key, sep, value = pair.partition("=")
            if sep:
                headers[key.strip()] = value.strip()

    resource = Resource.create({
        "service.name": "blob-ingestion-service",
        #Optional: add more resource attributes here
        "service.version": os.getenv("SERVICE_VERSION", "1.0.0"),
        "deployment.environment": os.getenv("DEPLOYMENT_ENVIRONMENT", "deve"),
        }
    )


    tracer_provider = TracerProvider(resource=resource)

    if endpoint:
        span_exporter = OTLPSpanExporter(endpoint=endpoint, headers=headers)
        tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
        trace.set_tracer_provider(tracer_provider)

        metric_exporter = OTLPMetricExporter(endpoint=endpoint, headers=headers)
        reader = PeriodicExportingMetricReader(metric_exporter)
        meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(meter_provider)
    else:
        # No exporter configured — set providers without external exporters
        trace.set_tracer_provider(tracer_provider)
        meter_provider = MeterProvider(resource=resource)
        metrics.set_meter_provider(meter_provider)


    def shutdown_otel():
        # Make shutdown idempotent: skip if already executed
        if getattr(shutdown_otel, "_called", False):
            return
        shutdown_otel._called = True

        logger.info("Shutting down OpenTelemetry...")
        try:
            try:
                tracer_provider.shutdown()
            except Exception:
                logger.exception("Error shutting down tracer provider")
            try:
                meter_provider.shutdown()
            except Exception:
                logger.exception("Error shutting down meter provider")
            logger.info("OpenTelemetry shut down successfully.")
        except Exception as e:
            logger.exception(f"Error during OpenTelemetry shutdown: {e}")

    # Registrar o shutdown para ser executado no encerramento do processo
    atexit.register(shutdown_otel)

    return tracer_provider, meter_provider, shutdown_otel
