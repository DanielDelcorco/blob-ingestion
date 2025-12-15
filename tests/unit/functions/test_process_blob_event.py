from unittest.mock import MagicMock, patch
import json
import azure.functions as func

from function_app import processBlobEvent
from app.core.models.ingestion_settings import FileType


class DummyHttpRequest:
    def __init__(self, body_dict: dict, headers: dict | None = None):
        self._body_dict = body_dict
        self.headers = headers or {}

    def get_json(self):
        return self._body_dict


def test_process_blob_event_happy_path(monkeypatch):
    """Testa o fluxo feliz com um request HTTP válido"""
    req = DummyHttpRequest({"fileType": FileType.DEFAULT_GROUP})

    with patch(
        "function_app.IngestionService.run",
        return_value=100,
    ) as run_mock:
        response = processBlobEvent(req)

        assert response.status_code == 200
        assert run_mock.called

        body = json.loads(response.get_body())
        assert body["status"] == "success"
        assert body["fileType"] == "default_group"
        assert body["docsProcessed"] == 100


def test_process_blob_event_missing_file_type():
    """Testa request sem 'fileType'"""
    req = DummyHttpRequest({})
    
    response = processBlobEvent(req)

    assert response.status_code == 400
    body = json.loads(response.get_body())
    assert "Missing 'fileType'" in body["error"]


def test_process_blob_event_invalid_file_type():
    """Testa request com tipo de arquivo inválido"""
    req = DummyHttpRequest({"fileType": "invalid_type"})
    
    response = processBlobEvent(req)

    assert response.status_code == 400
    body = json.loads(response.get_body())
    assert "não suportado" in body["error"]


def test_process_blob_event_missing_credentials():
    """Testa quando credenciais do Blob não estão configuradas"""
    req = DummyHttpRequest({"fileType": FileType.DEFAULT_GROUP})
    
    with patch(
        "function_app.IngestionService.run",
        side_effect=ValueError("Azure Blob Storage credentials not configured"),
    ):
        response = processBlobEvent(req)

        assert response.status_code == 500
        body = json.loads(response.get_body())
        assert "errorCode" in body
