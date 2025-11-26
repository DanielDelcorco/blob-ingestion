from typing import List

from pymongo import MongoClient, UpdateOne
from logging import Logger
from opentelemetry import trace, metrics

from app.core.models.mongo_settings import MongoSettings

tracer = trace.get_tracer(__name__)


class MongoWriter:
    def __init__(self, settings: MongoSettings, logger: Logger):
        self._settings = settings
        self._logger = logger
        self._client = MongoClient(settings.uri, tls=False)
        self._collection = self._client[settings.database][settings.collection]

        # Only initialized when instantiated via __init__
        self._meter = metrics.get_meter(__name__)
        self._docs_counter = self._meter.create_counter("mongo_docs_upserted_total")
        self._error_counter = self._meter.create_counter("mongo_upsert_errors_total")

    # ✅ Ensures metrics exist even if __init__ wasn't executed (e.g., in unit tests using __new__)
    def _ensure_metrics(self):
        if not hasattr(self, "_meter"):
            self._meter = metrics.get_meter(__name__)
        if not hasattr(self, "_docs_counter"):
            self._docs_counter = self._meter.create_counter("mongo_docs_upserted_total")
        if not hasattr(self, "_error_counter"):
            self._error_counter = self._meter.create_counter("mongo_upsert_errors_total")

    def close(self):
        try:
            self._client.close()
        except Exception:
            # Log but do not raise — close() must be safe
            self._logger.exception("event=mongo_close_failed")

    def upsert_many(self, docs: List[dict], key_fields: List[str]) -> int:
        if not docs:
            return 0

        # ✅ Make sure metrics exist
        self._ensure_metrics()

        with tracer.start_as_current_span("mongo_bulk_upsert"):
            try:
                operations = [
                    UpdateOne(
                        {"_id": {field: doc[field] for field in key_fields}},
                        {"$set": doc},
                        upsert=True,
                    )
                    for doc in docs
                ]

                result = self._collection.bulk_write(operations, ordered=False)

                total = len(operations)
                self._docs_counter.add(total)
                self._logger.info(f"event=chunk_upserted total_docs={total}")

                return total

            except Exception:
                self._error_counter.add(1)
                self._logger.exception("event=mongo_upsert_failed")
                raise

    def delete_older_than(self, reference_date: str) -> int:
        with tracer.start_as_current_span("mongo_delete_old_docs"):
            result = self._collection.delete_many({"referenceDate": {"$lt": reference_date}})
            deleted = result.deleted_count or 0
            self._logger.info(f"event=delete_old_docs deleted={deleted}")
            return deleted