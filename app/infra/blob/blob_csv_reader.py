from io import StringIO
from typing import Iterable

import pandas as pd
from azure.storage.blob import BlobClient
from logging import Logger
from opentelemetry import trace

from app.core.models.file_schema import FileSchema
from app.core.models.ingestion_settings import IngestionSettings

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
            iterator = stream.chunks()
            buffer = ""
            for raw_chunk in iterator:
                buffer += raw_chunk.decode(self._settings.encoding)
                size_mb = len(buffer) / (1024 * 1024)
                self._logger.info(f"event=buffer_growth buffer_mb={size_mb:.2f}")
                if size_mb >= 5:
                    yield from self._consume(buffer)
                    buffer = ""
            if buffer:
                yield from self._consume(buffer)

    def _consume(self, buffer: str):
        with tracer.start_as_current_span("parse_csv_buffer"):
            buffer_stream = StringIO(buffer)
            for chunk in pd.read_csv(
                buffer_stream,
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
