from unittest.mock import MagicMock, patch
import json
import azure.functions as func

from functions.process_blob_event import process_blob_event


class DummyHttpRequest:
    def __init__(self, body_dict: dict):
        self._body_dict = body_dict

    def get_json(self):
        return self._body_dict


def test_process_blob_event_happy_path(monkeypatch):
    """Testa o fluxo feliz com um request HTTP válido"""
    req = DummyHttpRequest({"fileType": "default_group"})

    fake_blob_client = MagicMock()
    fake_mongo_writer = MagicMock()

    with patch(
        "functions.process_blob_event.BlobClientFactory.create",
        return_value=fake_blob_client,
    ), patch(
        "functions.process_blob_event.MongoClientFactory.create",
        return_value=fake_mongo_writer,
    ), patch(
        "functions.process_blob_event.IngestionService.run",
        return_value=100,
    ) as run_mock:
        response = process_blob_event(req)
        
        assert response.status_code == 200
        assert run_mock.called
        
        body = json.loads(response.get_body())
        assert body["status"] == "success"
        assert body["fileType"] == "default_group"
        assert body["docsProcessed"] == 100


def test_process_blob_event_missing_file_type():
    """Testa request sem 'fileType'"""
    req = DummyHttpRequest({})
    
    response = process_blob_event(req)
    
    assert response.status_code == 400
    body = json.loads(response.get_body())
    assert "Missing 'fileType'" in body["error"]


def test_process_blob_event_invalid_file_type():
    """Testa request com tipo de arquivo inválido"""
    req = DummyHttpRequest({"fileType": "invalid_type"})
    
    response = process_blob_event(req)
    
    assert response.status_code == 400
    body = json.loads(response.get_body())
    assert "não suportado" in body["error"]


def test_process_blob_event_missing_credentials():
    """Testa quando credenciais do Blob não estão configuradas"""
    req = DummyHttpRequest({"fileType": "default_group"})
    
    with patch(
        "functions.process_blob_event.BlobClientFactory.create",
        side_effect=ValueError("Azure Blob Storage credentials not configured"),
    ):
        response = process_blob_event(req)
        
        assert response.status_code == 500
        body = json.loads(response.get_body())
        assert "credentials not configured" in body["error"]
