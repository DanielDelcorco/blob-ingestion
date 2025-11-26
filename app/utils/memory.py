import psutil
from logging import Logger
from opentelemetry import metrics


class MemoryObserver:
    def __init__(self, logger: Logger):
        self._logger = logger
        meter = metrics.get_meter(__name__)
        self._memory_gauge = meter.create_observable_gauge(
            "process_memory_mb",
            callbacks=[self._observe],
            unit="MB"
        )

    def _observe(self, _):
        mem_mb = psutil.Process().memory_info().rss / (1024 * 1024)
        self._logger.info(f"event=memory_usage memory_mb={mem_mb:.2f}")
        return []

    def log_now(self):
        mem_mb = psutil.Process().memory_info().rss / (1024 * 1024)
        self._logger.info(f"event=memory_usage memory_mb={mem_mb:.2f}")
