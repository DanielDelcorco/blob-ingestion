from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED, as_completed
from datetime import datetime, UTC
import gc

from logging import Logger
from opentelemetry import trace, metrics

from app.core.models.ingestion_settings import IngestionSettings
from app.infra.blob.blob_csv_reader import BlobCsvReader
from app.infra.mongo.mongo_writer import MongoWriter
from app.utils.memory import MemoryObserver

tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

class IngestionService:
    def __init__(self, settings: IngestionSettings, logger: Logger):
        self._settings = settings
        self._logger = logger

        self._docs_counter = meter.create_counter("docs_ingested_total")
        self._chunk_counter = meter.create_counter("chunks_processed_total")
        self._latency_histogram = meter.create_histogram(
            name="ingestion_latency_seconds",
            unit="s",
            description="Latency of ingestion process in seconds"
        )
        self._memory_observer = MemoryObserver(logger)
        self._reader = BlobCsvReader(settings, logger)
        self._writer = MongoWriter(settings.mongo, logger)

    def _submit(self, executor, docs):
        return executor.submit(
            self._writer.upsert_many,
            list(docs),
            self._key_fields,
        )

    def run(self) -> int:
        start = datetime.now(UTC)
        total_docs = 0

        with tracer.start_as_current_span("ingestion_service"):
            with ThreadPoolExecutor(max_workers=self._settings.max_workers) as executor:
                futures = []
                for chunk in self._reader.iter_chunks():
                    docs = chunk.to_dict(orient="records")
                    self._chunk_counter.add(1)
                    futures.append(self._submit(executor, docs))

                    if len(futures) >= self._settings.max_workers:
                        done, pending = wait(futures, return_when=ALL_COMPLETED)
                        futures = list(pending)
                        for f in done:
                            count = f.result()
                            total_docs += count
                            self._docs_counter.add(count)
                            self._memory_observer.log_now()
                            gc.collect()

                for f in as_completed(futures):
                    count = f.result()
                    total_docs += count
                    self._docs_counter.add(count)
                    self._memory_observer.log_now()
                    gc.collect()

            elapsed = (datetime.now(UTC) - start).total_seconds()
            self._logger.info(f"event=ingestion_finished total_docs={total_docs} elapsed_s={elapsed:.2f}")
            return total_docs
