from unittest.mock import MagicMock
import pandas as pd

from app.core.models.ingestion_settings import IngestionSettings
from app.core.services.ingestion_service import IngestionService


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

    settings = IngestionSettings(chunk_size=2, max_workers=2)
    logger = MagicMock()

    service = IngestionService(
        reader=reader,
        writer=writer,
        settings=settings,
        logger=logger,
        correlation_id="corr-123",
    )

    total_docs = service.run()

    assert total_docs == 6
    assert writer.upsert_many.call_count == 3
