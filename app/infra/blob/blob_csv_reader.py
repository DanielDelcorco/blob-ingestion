from typing import Iterable

import pandas as pd
from azure.storage.blob import BlobClient
from logging import Logger
from opentelemetry import trace
from datetime import datetime, UTC

from app.core.models.ingestion_settings import IngestionSettings
from app.infra.blob.StreamWrapper import StreamWrapper

tracer = trace.get_tracer(__name__)


class BlobCsvReader:
    def __init__(self, settings: IngestionSettings, logger: Logger):
        self._settings = settings
        self._logger = logger
        self._schema = self._settings.schema
        self._blob_client = self._create_blob_client()


    def _create_blob_client(self) -> BlobClient:
        blob_settings = self._settings.blob
        blob_client = BlobClient(
            account_url=blob_settings.account_url,
            container_name=blob_settings.container_name,
            blob_name=f"{blob_settings.input_path}{blob_settings.file_name}",
            credential=blob_settings.account_key,
        )
        return blob_client

    def iter_chunks(self) -> Iterable[pd.DataFrame]:
        with tracer.start_as_current_span("blob_download_and_parse"):
            stream = self._blob_client.download_blob()
            buffer = StreamWrapper(stream, encoding=self._settings.encoding)

            for chunk in pd.read_csv(
                buffer,
                usecols=list(self._schema.column_mapping.keys()),
                chunksize=self._settings.chunk_size,
                sep=self._schema.sep,
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
        # Add ingestion metadata columns expected by downstream processing
        chunk["referenceDate"] = self._settings.reference_date
        chunk["updateDate"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.000+00:00")
