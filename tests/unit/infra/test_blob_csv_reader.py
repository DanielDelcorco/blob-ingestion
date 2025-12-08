from unittest.mock import MagicMock
from app.core.models.file_schema import FileSchema
from app.core.models.ingestion_settings import IngestionSettings
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

    settings = IngestionSettings(chunk_size=10, max_workers=1)
    logger = MagicMock()

    reader = BlobCsvReader(blob_client, schema, settings, logger)

    chunks = list(reader.iter_chunks())
    assert len(chunks) == 1

    df = chunks[0]
    assert set(df.columns) == {"code", "flag", "referenceDate", "updateDate"}
    assert df["code"].tolist() == [1, 2]
    assert df["flag"].tolist() == [True, False]
    assert "referenceDate" in df.columns
    assert "updateDate" in df.columns
