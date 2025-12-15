from unittest.mock import MagicMock

from app.core.models.ingestion_settings import MongoSettings
from app.infra.mongo.mongo_writer import MongoWriter


def test_mongo_writer_calls_bulk_write_with_expected_operations():
    mock_collection = MagicMock()
    mock_db = {"test_collection": mock_collection}
    mock_client = MagicMock()
    mock_client.__getitem__.return_value = mock_db

    settings = MongoSettings(
        uri="mongodb://localhost:27017",
        database="test_db",
        collection="test_collection",
    )

    logger = MagicMock()

    writer = MongoWriter.__new__(MongoWriter)
    writer._settings = settings
    writer._logger = logger
    writer._client = mock_client
    writer._collection = mock_collection

    docs = [{"defaultGroupId": "G1", "documentId": "D1"}]

    count = writer.upsert_many(docs, ["defaultGroupId", "documentId"])

    assert count == 1
    assert mock_collection.bulk_write.called
