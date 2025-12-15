from unittest.mock import MagicMock
import pandas as pd

from app.core.models.ingestion_settings import IngestionSettings, FileSchema, BlobSettings, MongoSettings
from app.core.services.ingestion_service import IngestionService
from unittest.mock import patch


class DummyReader:
    def __init__(self, chunks):
        self._chunks = chunks

    def iter_chunks(self):
        for c in self._chunks:
            yield c


def test_ingestion_service_runs_and_counts_docs():
    chunks = [
        pd.DataFrame([{"a": 1}, {"a": 2}]),
        pd.DataFrame([{"a": 3}, {"a": 4}]),
        pd.DataFrame([{"a": 5}, {"a": 6}]),
    ]
    reader = DummyReader(chunks)

    writer = MagicMock()
    writer.upsert_many.side_effect = [2, 2, 2]

    settings = IngestionSettings(
        chunk_size=2,
        max_workers=2,
        encoding="cp1252",
        schema=FileSchema(name="test", column_mapping={"a": "a"}, boolean_cols=[], key_fields=["a"]),
        mongo=MongoSettings(uri="mongodb://localhost:27017", database="db", collection="col"),
        blob=BlobSettings(
            account_url="http://localhost:10000/",
            account_key="key",
            container_name="devstoreaccount1",
            input_path="input/",
            processed_path="processed/",
            file_name="f.csv",
        ),
        reference_date="2025-12-14T00:00:00.000+00:00",
    )
    logger = MagicMock()

    # Patch the internal reader/writer that the refactored IngestionService creates
    with patch("app.core.services.ingestion_service.BlobCsvReader", return_value=reader), patch(
        "app.core.services.ingestion_service.MongoWriter", return_value=writer
    ):
        service = IngestionService(settings, logger)
        # allow tests to inject mocked reader/writer
        service._reader = reader
        service._writer = writer

    total_docs = service.run()

    assert total_docs == 6
    assert writer.upsert_many.call_count == 3
