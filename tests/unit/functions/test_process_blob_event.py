from unittest.mock import MagicMock, patch

from functions.process_blob_event import process_blob_event


class DummyMessage:
    def __init__(self, body: str, cid: str = "cid-1"):
        self._body = body
        self.correlation_id = cid
        self.message_id = cid

    def get_body(self):
        return self._body.encode("utf-8")


def test_process_blob_event_happy_path(monkeypatch):
    msg = DummyMessage(body='{"data": {"url": "https://example.com/blob.csv"}}')

    fake_blob_client = MagicMock()

    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")

    with patch(
        "functions.process_blob_event.BlobClient.from_blob_url",
        return_value=fake_blob_client,
    ), patch(
        "functions.process_blob_event.IngestionService.run",
        return_value=0,
    ) as run_mock, patch(
        "functions.process_blob_event.MongoWriter.delete_older_than",
        return_value=0,
    ), patch(
        "functions.process_blob_event.MongoWriter.close",
        return_value=None,
    ):
        process_blob_event(msg)
        assert run_mock.called
