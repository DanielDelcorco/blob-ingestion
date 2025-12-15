from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED, as_completed
from datetime import datetime, UTC
import gc
from typing import Optional

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

        # Metrics
        self._docs_counter = meter.create_counter("docs_ingested_total")
        self._chunk_counter = meter.create_counter("chunks_processed_total")
        self._latency_histogram = meter.create_histogram(
            name="ingestion_latency_seconds",
            unit="s",
            description="Latency of ingestion process in seconds"
        )

        self._memory_observer = MemoryObserver(logger)

        # Defer creation of IO-bound components to `run()` so construction is lightweight
        # and safe for unit tests that patch `run`.
        self._reader: Optional[BlobCsvReader] = None
        self._writer: Optional[MongoWriter] = None

        # NOTE: do not infer or set default key fields here — different file types
        # have different key fields and they should come from the configured schema.
        # The service will validate and read `schema.key_fields` at `run()` time.

    def _submit(self, executor, docs):
        assert self._writer is not None, "writer not initialized"
        return executor.submit(
            self._writer.upsert_many,
            list(docs),
            self._key_fields,
        )
    
    def delete(self):
        assert self._writer is not None, "writer not initialized"
        self._writer.delete_older_than(self._settings.reference_date)

    def close(self):
        # close() is idempotent on the writer side; guard if not initialized.
        if self._writer is None:
            return
        self._writer.close()

    def run(self) -> int:
        start = datetime.now(UTC)
        total_docs = 0

        # Validate and obtain key fields from schema at runtime — this ensures
        # the service uses the per-file-type configuration and avoids hidden
        # defaults inside the service.
        key_fields = getattr(self._settings.schema, "key_fields", None)
        if not key_fields:
            raise ValueError("schema.key_fields must be configured for this file type")
        self._key_fields = list(key_fields)

        # Lazily create IO components from settings when not injected (testable)
        if self._reader is None:
            self._reader = BlobCsvReader(self._settings, self._logger)
        if self._writer is None:
            # MongoWriter accepts MongoSettings (self._settings.mongo)
            self._writer = MongoWriter(self._settings.mongo, self._logger)

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
