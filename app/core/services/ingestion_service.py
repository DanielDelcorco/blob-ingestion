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
        # Wrap the upsert call in a traced task so each batch has its own span.
        def _task(batch):
            with tracer.start_as_current_span("ingestion.upsert_batch") as span:
                span.set_attribute("batch_size", len(batch))
                # key fields are low-cardinality and useful for debugging
                span.set_attribute("key_fields", ",".join(self._key_fields))
                try:
                    count = self._writer.upsert_many(list(batch), self._key_fields)
                    span.add_event("upsert_result", {"count": count})
                    return count
                except Exception as e:
                    # Record exception in the span and re-raise so caller handles it
                    try:
                        span.record_exception(e)
                        span.set_attribute("error", True)
                        span.add_event("exception", {"type": type(e).__name__, "msg": str(e)})
                    except Exception:
                        # best-effort tracing; do not mask original exception
                        pass
                    raise

        return executor.submit(_task, docs)
    
    def delete(self):
        # If writer isn't initialized there's nothing to delete.
        if self._writer is None:
            return

        with tracer.start_as_current_span("ingestion.delete_old_docs") as span:
            # Record the cutoff used for deletion; cast to str for safe span attribute types
            span.set_attribute("reference_date", str(self._settings.reference_date))
            try:
                deleted = self._writer.delete_older_than(self._settings.reference_date)
                # Add an event to the span with the deleted count for tracing
                span.add_event("delete_result", {"deleted": deleted})

                # Log how many documents were removed by the cleanup step for observability
                self._logger.info(
                    f"event=delete_old_docs_completed reference_date={self._settings.reference_date} deleted={deleted}"
                )
            except Exception as e:
                # Best-effort: record exception on span and log, but do not re-raise
                try:
                    span.record_exception(e)
                    span.set_attribute("error", True)
                    span.add_event("exception", {"type": type(e).__name__, "msg": str(e)})
                except Exception:
                    pass
                self._logger.debug("delete_older_than failed", exc_info=True)

    def close(self):
        # close() is idempotent on the writer side; guard if not initialized.
        if self._writer is None:
            return
        with tracer.start_as_current_span("ingestion.close") as span:
            try:
                self._writer.close()
                span.add_event("closed_writer")
            except Exception as e:
                try:
                    span.record_exception(e)
                    span.set_attribute("error", True)
                except Exception:
                    pass
                # still log and do not re-raise to avoid masking upstream cleanup
                self._logger.debug("writer.close() failed", exc_info=True)

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

        try:
            with tracer.start_as_current_span("ingestion_service") as span:
                with ThreadPoolExecutor(max_workers=self._settings.max_workers) as executor:
                    futures = []
                    chunk_index = 0
                    for chunk in self._reader.iter_chunks():
                        docs = chunk.to_dict(orient="records")
                        self._chunk_counter.add(1)
                        # Trace reading/processing of this chunk
                        with tracer.start_as_current_span("ingestion.read_chunk") as read_span:
                            read_span.set_attribute("chunk_index", chunk_index)
                            read_span.set_attribute("rows", len(docs))
                            futures.append(self._submit(executor, docs))
                        chunk_index += 1

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
            span.set_attribute("docs_processed", total_docs)
            span.set_attribute("total_chunks", chunk_index)
            span.set_attribute("elapsed_s", elapsed)
            return total_docs
        finally:
            # Ensure cleanup step runs even if run() raises; delete is idempotent.
            try:
                self.delete()
            except Exception:
                self._logger.debug("service.delete() failed during run() finally", exc_info=True)
