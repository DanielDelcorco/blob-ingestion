import contextvars
import http
import logging
from opentelemetry import trace, baggage


_correlation_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("correlation_id", default=None)


def get_correlation_id() -> str | None:
    return _correlation_id_ctx.get()

def set_correlation_id(correlation_id: str | None) -> None:
    _correlation_id_ctx.set(correlation_id)


def _format_trace_id(trace_id: int) -> str:
    return f"{trace_id:032x}"

def _format_span_id(span_id: int) -> str:
    return f"{span_id:016x}"

class OTelTraceFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            span = trace.get_current_span()
            ctx = span.get_span_context() if span else None
            if ctx and ctx.is_valid:
                record.trace_id = _format_trace_id(ctx.trace_id)
                record.span_id = _format_span_id(ctx.span_id)
            else:
                record.trace_id = None
                record.span_id = None
            
            corr = get_correlation_id()
            
            if corr is None:
                b = baggage.get_all()
                corr = b.get("correlation_id")
            
            if corr is None and getattr(record, "trace_id", None):
                corr = record.trace_id

            record.correlation_id = corr
        except Exception:
            record.trace_id = getattr(record, "trace_id", None)
            record.span_id = getattr(record, "span_id", None)
            record.correlation_id = getattr(record, "correlation_id", None)
        return True


def configure_logging() -> logging.Logger:
    logging.basicConfig(
        level=logging.WARNING,
        force=True
    )

    logger = logging.getLogger("blob_ingestion")
    logger.setLevel(logging.INFO)

    logger.propagate = False

    if not logger.hasHandlers():
        handler = logging.StreamHandler()

        fmt = (
            "%(asctime)s %(levelname)s %(name)s %(correlation_id)s "
            "%(trace_id)s %(span_id)s %(module)s %(funcName)s %(lineno)d %(message)s"
        )

        try:
            # import the moved module path when available
            from pythonjsonlogger import json as _jsonlogger
            formatter = _jsonlogger.JsonFormatter(fmt)
        except Exception:
            try:
                from pythonjsonlogger import jsonlogger as _jsonlogger
                formatter = _jsonlogger.JsonFormatter(fmt)
            except Exception:
                formatter = logging.Formatter(fmt)

        handler.setFormatter(formatter)
        handler.addFilter(OTelTraceFilter())
        logger.addHandler(handler)

        logging.getLogger("azure.core.pipeline.policies").setLevel(logging.WARNING)
        logging.getLogger("azure.storage.blob").setLevel(logging.WARNING)
        logging.getLogger("pymongo").setLevel(logging.WARNING)

        http.client.HTTPConnection.debuglevel = 1

        logging.basicConfig(level=logging.INFO)

    return logger

