from unittest.mock import MagicMock, patch
from app.core.models.ingestion_settings import FileSchema, IngestionSettings, BlobSettings, MongoSettings
from app.infra.blob.blob_csv_reader import BlobCsvReader


class FakeBlobDownload:
    def __init__(self, chunks):
        self._chunks = chunks

    def chunks(self):
        for c in self._chunks:
            yield c


class FakeBlobClient:
    def __init__(self, chunks):
        self._chunks = chunks

    def download_blob(self):
        return FakeBlobDownload(self._chunks)


def test_blob_csv_reader_applies_schema_and_boolean():
    csv_data = "cod;flag\n1;S\n2;N\n"
    blob_client = FakeBlobClient([csv_data.encode("cp1252")])

    schema = FileSchema(
        name="test",
        column_mapping={"cod": "code", "flag": "flag"},
        boolean_cols=["flag"],
    )

    settings = IngestionSettings(
        chunk_size=10,
        max_workers=1,
        encoding="cp1252",
        schema=schema,
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

    # Patch the internal blob client creation to return our fake client
    with patch.object(BlobCsvReader, "_create_blob_client", return_value=blob_client):
        reader = BlobCsvReader(settings, logger)
        chunks = list(reader.iter_chunks())
    assert len(chunks) == 1

    df = chunks[0]
    assert set(df.columns) == {"code", "flag", "referenceDate", "updateDate"}
    assert df["code"].tolist() == [1, 2]
    assert df["flag"].tolist() == [True, False]
    assert "referenceDate" in df.columns
    assert "updateDate" in df.columns
