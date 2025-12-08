import pandas as pd
from azure.storage.blob import BlobClient
from logging import Logger
from opentelemetry import trace
from datetime import datetime, UTC
from typing import Iterable
from app.core.models.file_schema import FileSchema
from app.core.models.ingestion_settings import IngestionSettings
from app.infra.blob.StreamWrapper import StreamWrapper

tracer = trace.get_tracer(__name__)


class BlobCsvReader:
    def __init__(self, blob_client: BlobClient, schema: FileSchema, settings: IngestionSettings, logger: Logger):
        self._blob_client = blob_client
        self._schema = schema
        self._settings = settings
        self._logger = logger

    def iter_chunks(self) -> Iterable[pd.DataFrame]:
        with tracer.start_as_current_span("blob_download_and_parse"):
            stream = self._blob_client.download_blob()
            buffer = StreamWrapper(stream, encoding=self._settings.encoding)

            for chunk in pd.read_csv(
                buffer,
                usecols=list(self._schema.column_mapping.keys()),
                chunksize=self._settings.chunk_size,
                sep=";",
            ):
                self._normalize(chunk)
                yield chunk

    def _normalize(self, chunk: pd.DataFrame) -> None:
        chunk.rename(columns=self._schema.column_mapping, inplace=True)
        for col in chunk.select_dtypes(include=["object"]).columns:
            chunk[col] = chunk[col].str.strip()
        for col in self._schema.boolean_cols:
            if col in chunk.columns:
                chunk[col] = chunk[col].eq("S")
        chunk["referenceDate"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.000+00:00")
        chunk["updateDate"] = datetime.now(UTC)
