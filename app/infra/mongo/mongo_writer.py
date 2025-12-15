from typing import List, Optional

import time
from pymongo import MongoClient, UpdateOne
from pymongo.errors import AutoReconnect, NetworkTimeout
from logging import Logger
from opentelemetry import trace, metrics

from app.core.models.ingestion_settings import MongoSettings


tracer = trace.get_tracer(__name__)


class MongoWriter:
    def __init__(self, settings: MongoSettings, logger: Logger):
        self._settings = settings
        self._logger = logger
        # client and collection are created lazily from settings
        self._client: Optional[MongoClient] = None
        self._collection = None

        # Metrics
        self._meter = metrics.get_meter(__name__)
        self._docs_counter = self._meter.create_counter("mongo_docs_upserted_total")
        self._error_counter = self._meter.create_counter("mongo_upsert_errors_total")

    def _ensure_client(self):
        if getattr(self, "_client", None) is None:
            # Keep tls=False for local/dev (matches earlier behavior); in production
            # callers should provide a client via constructor if different options required.
            self._client = MongoClient(self._settings.uri, tls=False)
        if getattr(self, "_collection", None) is None:
            self._collection = self._client[self._settings.database][self._settings.collection]

    def _ensure_metrics(self):
        if not hasattr(self, "_meter"):
            self._meter = metrics.get_meter(__name__)
        if not hasattr(self, "_docs_counter"):
            self._docs_counter = self._meter.create_counter("mongo_docs_upserted_total")
        if not hasattr(self, "_error_counter"):
            self._error_counter = self._meter.create_counter("mongo_upsert_errors_total")

    def close(self):
        try:
            if getattr(self, "_client", None):
                self._client.close()
        except Exception:
            self._logger.exception("event=mongo_close_failed")
        finally:
            # make idempotent
            self._client = None
            self._collection = None

    def upsert_many(self, docs: List[dict], key_fields: List[str], max_retries: int = 3) -> int:
        if not docs:
            return 0

        # Validate key fields presence
        if not key_fields:
            raise ValueError("key_fields must be provided for upsert")

        for doc in docs:
            for k in key_fields:
                if k not in doc:
                    raise ValueError(f"Document missing key field '{k}'")

        self._ensure_metrics()
        self._ensure_client()

        operations = [
            UpdateOne({field: doc[field] for field in key_fields}, {"$set": doc}, upsert=True)
            for doc in docs
        ]

        attempt = 0
        while True:
            attempt += 1
            with tracer.start_as_current_span("mongo_bulk_upsert") as span:
                span.set_attribute("attempt", attempt)
                span.set_attribute("docs", len(docs))
                try:
                    result = self._collection.bulk_write(operations, ordered=False)
                    total = len(operations)
                    # add db/collection labels to metrics
                    self._docs_counter.add(total, {"database": self._settings.database, "collection": self._settings.collection})
                    self._logger.info(f"event=chunk_upserted total_docs={total}")
                    return total

                except (AutoReconnect, NetworkTimeout) as e:
                    span.record_exception(e)
                    if attempt >= max_retries:
                        self._error_counter.add(1)
                        self._logger.exception("event=mongo_upsert_failed after retries")
                        raise
                    backoff = 0.5 * (2 ** (attempt - 1))
                    time.sleep(backoff)
                    continue
                except Exception as e:
                    span.record_exception(e)
                    self._error_counter.add(1)
                    self._logger.exception("event=mongo_upsert_failed")
                    raise

    def delete_older_than(self, reference_date: str) -> int:
        self._ensure_client()
        with tracer.start_as_current_span("mongo_delete_old_docs"):
            result = self._collection.delete_many({"referenceDate": {"$lt": reference_date}})
            deleted = result.deleted_count or 0
            self._logger.info(f"event=delete_old_docs deleted={deleted}")
            return deleted