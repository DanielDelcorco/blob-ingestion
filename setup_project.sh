#!/bin/bash

echo "📁 Creating folder structure..."

mkdir -p app/config
mkdir -p app/core/models
mkdir -p app/core/services
mkdir -p app/infra/blob
mkdir -p app/infra/mongo
mkdir -p app/utils
mkdir -p functions/process_blob_event
mkdir -p tests/unit/core
mkdir -p tests/unit/infra
mkdir -p tests/unit/functions
mkdir -p tests/fixtures

echo "✅ Folders created."


########################################
# FILE: app/__init__.py
########################################
cat << 'EOF' > app/__init__.py
# Makes "app" a package
EOF


########################################
# FILE: app/config/logging_config.py
########################################
cat << 'EOF' > app/config/logging_config.py
import logging


def configure_logging() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    logging.getLogger("azure.core.pipeline.policies").setLevel(logging.WARNING)
    logging.getLogger("azure.storage.blob").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    return logging.getLogger("blob_ingestion")
EOF


########################################
# FILE: app/config/otel.py
########################################
cat << 'EOF' > app/config/otel.py
import os

from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader


def setup_otel():
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    resource = Resource.create({"service.name": "blob-ingestion-service"})

    tracer_provider = TracerProvider(resource=resource)
    span_exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(tracer_provider)

    metric_exporter = OTLPMetricExporter(endpoint=endpoint, insecure=True)
    reader = PeriodicExportingMetricReader(metric_exporter)
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(meter_provider)
EOF


########################################
# FILE: app/core/models/file_schema.py
########################################
cat << 'EOF' > app/core/models/file_schema.py
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class FileSchema:
    name: str
    column_mapping: Dict[str, str]
    boolean_cols: List[str]
EOF


########################################
# FILE: app/core/models/ingestion_settings.py
########################################
cat << 'EOF' > app/core/models/ingestion_settings.py
from dataclasses import dataclass


@dataclass
class IngestionSettings:
    chunk_size: int = 50_000
    max_workers: int = 5
    encoding: str = "cp1252"
EOF


########################################
# FILE: app/core/models/mongo_settings.py
########################################
cat << 'EOF' > app/core/models/mongo_settings.py
from dataclasses import dataclass


@dataclass
class MongoSettings:
    uri: str
    database: str
    collection: str
EOF


########################################
# FILE: app/utils/memory.py
########################################
cat << 'EOF' > app/utils/memory.py
import psutil
from logging import Logger
from opentelemetry import metrics


class MemoryObserver:
    def __init__(self, logger: Logger):
        self._logger = logger
        meter = metrics.get_meter(__name__)
        self._memory_gauge = meter.create_observable_gauge(
            "process_memory_mb",
            callbacks=[self._observe],
            unit="MB"
        )

    def _observe(self, _):
        mem_mb = psutil.Process().memory_info().rss / (1024 * 1024)
        self._logger.info(f"event=memory_usage memory_mb={mem_mb:.2f}")
        return []

    def log_now(self):
        mem_mb = psutil.Process().memory_info().rss / (1024 * 1024)
        self._logger.info(f"event=memory_usage memory_mb={mem_mb:.2f}")
EOF


########################################
# FILE: app/infra/blob/blob_csv_reader.py
########################################
cat << 'EOF' > app/infra/blob/blob_csv_reader.py
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
EOF


########################################
# FILE: app/infra/mongo/mongo_writer.py
########################################
cat << 'EOF' > app/infra/mongo/mongo_writer.py
from typing import List

from pymongo import MongoClient, UpdateOne
from logging import Logger
from opentelemetry import trace, metrics

from app.core.models.mongo_settings import MongoSettings

tracer = trace.get_tracer(__name__)


class MongoWriter:
    def __init__(self, settings: MongoSettings, logger: Logger):
        self._settings = settings
        self._logger = logger
        self._client = MongoClient(settings.uri, tls=False)
        self._collection = self._client[settings.database][settings.collection]

        meter = metrics.get_meter(__name__)
        self._docs_counter = meter.create_counter("mongo_docs_upserted_total")
        self._error_counter = meter.create_counter("mongo_upsert_errors_total")

    def close(self):
        self._client.close()

    def upsert_many(self, docs: List[dict], key_fields: List[str]) -> int:
        if not docs:
            return 0

        with tracer.start_as_current_span("mongo_bulk_upsert"):
            try:
                operations = [
                    UpdateOne(
                        {"_id": {field: doc[field] for field in key_fields}},
                        {"$set": doc},
                        upsert=True,
                    )
                    for doc in docs
                ]

                result = self._collection.bulk_write(operations, ordered=False)

                total = len(operations)
                self._docs_counter.add(total)
                self._logger.info(f"event=chunk_upserted total_docs={total}")
                return total
            except Exception:
                self._error_counter.add(1)
                self._logger.exception("event=mongo_upsert_failed")
                raise

    def delete_older_than(self, reference_date: str) -> int:
        with tracer.start_as_current_span("mongo_delete_old_docs"):
            result = self._collection.delete_many({"referenceDate": {"$lt": reference_date}})
            deleted = result.deleted_count or 0
            self._logger.info(f"event=delete_old_docs deleted={deleted}")
            return deleted
EOF


########################################
# FILE: app/core/services/ingestion_service.py
########################################
cat << 'EOF' > app/core/services/ingestion_service.py
from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED, as_completed
from datetime import datetime
import gc

from logging import Logger
from opentelemetry import trace, metrics

from app.core.models.ingestion_settings import IngestionSettings
from app.utils.memory import MemoryObserver

tracer = trace.get_tracer(__name__)


class IngestionService:
    def __init__(self, reader, writer, settings: IngestionSettings, logger: Logger, correlation_id: str):
        self._reader = reader
        self._writer = writer
        self._settings = settings
        self._logger = logger
        self._correlation_id = correlation_id

        meter = metrics.get_meter(__name__)
        self._docs_counter = meter.create_counter("docs_ingested_total")
        self._chunk_counter = meter.create_counter("chunks_processed_total")

        self._memory_observer = MemoryObserver(logger)

    def _submit(self, executor, docs):
        return executor.submit(
            self._writer.upsert_many,
            list(docs),
            ["defaultGroupId", "documentId"],
        )

    def run(self) -> int:
        start = datetime.utcnow()
        total_docs = 0

        with tracer.start_as_current_span("ingestion_service"):
            with ThreadPoolExecutor(max_workers=self._settings.max_workers) as executor:
                futures = []
                for chunk in self._reader.iter_chunks():
                    docs = chunk.to_dict(orient="records")
                    self._chunk_counter.add(1)
                    futures.append(self._submit(executor, docs))

                    if len(futures) >= self._settings.max_workers:
                        done, pending = wait(futures, return_when=ALL_COMPLETED)
                        futures = list(pending)
                        for f in done:
                            count = f.result()
                            total_docs += count
                            self._docs_counter.add(count)
                            self._memory_observer.log_now()
                            gc.collect()

                for f in as_completed(futures):
                    count = f.result()
                    total_docs += count
                    self._docs_counter.add(count)
                    self._memory_observer.log_now()
                    gc.collect()

            elapsed = (datetime.utcnow() - start).total_seconds()
            self._logger.info(f"event=ingestion_finished total_docs={total_docs} elapsed_s={elapsed:.2f}")
            return total_docs
EOF


########################################
# FILE: functions/process_blob_event/__init__.py
########################################
cat << 'EOF' > functions/process_blob_event/__init__.py
import json
import os
from datetime import datetime

import azure.functions as func
from azure.storage.blob import BlobClient
from opentelemetry import trace

from app.config.logging_config import configure_logging
from app.config.otel import setup_otel
from app.core.models.file_schema import FileSchema
from app.core.models.ingestion_settings import IngestionSettings
from app.core.models.mongo_settings import MongoSettings
from app.core.services.ingestion_service import IngestionService
from app.infra.blob.blob_csv_reader import BlobCsvReader
from app.infra.mongo.mongo_writer import MongoWriter

LOGGER = configure_logging()
setup_otel()
tracer = trace.get_tracer(__name__)

app = func.FunctionApp()

@app.function_name(name="processBlobEvent")
@app.service_bus_queue_trigger(
    arg_name="msg",
    connection="ServiceBusConnectionString",
    queue_name="blob-events",
)
def process_blob_event(msg: func.ServiceBusMessage):
    correlation_id = msg.correlation_id or msg.message_id

    with tracer.start_as_current_span("process_blob_event"):
        body = msg.get_body().decode("utf-8")
        event = json.loads(body)

        blob_url = event.get("data", {}).get("url")
        if not blob_url:
            LOGGER.error(f"event=missing_blob_url correlation_id={correlation_id}")
            return

        reference_date = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000+00:00")

        blob_client = BlobClient.from_blob_url(
            blob_url,
            credential=os.getenv("AZURE_BLOB_SAS_TOKEN")
        )

        mongo_settings = MongoSettings(
            uri=os.getenv("MONGO_URI", "mongodb://localhost:27017"),
            database=os.getenv("MONGO_DB_NAME", "slp"),
            collection=os.getenv("MONGO_COLLECTION_NAME", "defaultGroupDocument"),
        )

        schema = FileSchema(
            name="default_group",
            column_mapping={
                "cod_grupo_limite_posicao": "defaultGroupId",
                "nome_grupo_limite_posicao": "defaultGroupName",
                "cod_cobranca_automatica": "automaticMarginCall",
                "num_documento_integrante": "documentId",
            },
            boolean_cols=["automaticMarginCall"],
        )

        settings = IngestionSettings()

        reader = BlobCsvReader(blob_client, schema, settings, LOGGER)
        writer = MongoWriter(mongo_settings, LOGGER)
        service = IngestionService(reader, writer, settings, LOGGER, correlation_id)

        try:
            total_docs = service.run()
            writer.delete_older_than(reference_date)
            writer.close()
            LOGGER.info(f"event=process_blob_event_success total_docs={total_docs}")
        except:
            LOGGER.exception("event=process_blob_event_failed")
EOF


########################################
# FILE: tests/unit/core/test_ingestion_service.py
########################################
cat << 'EOF' > tests/unit/core/test_ingestion_service.py
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
EOF


########################################
# FILE: tests/unit/infra/test_blob_csv_reader.py
########################################
cat << 'EOF' > tests/unit/infra/test_blob_csv_reader.py
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
    assert list(df.columns) == ["code", "flag"]
    assert df["code"].tolist() == [1, 2]
    assert df["flag"].tolist() == [True, False]
EOF


########################################
# FILE: tests/unit/infra/test_mongo_writer.py
########################################
cat << 'EOF' > tests/unit/infra/test_mongo_writer.py
from unittest.mock import MagicMock

from app.core.models.mongo_settings import MongoSettings
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
EOF


########################################
# FILE: tests/unit/functions/test_process_blob_event.py
########################################
cat << 'EOF' > tests/unit/functions/test_process_blob_event.py
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
EOF


########################################
# FILE: tests/fixtures/sample_csv_small.csv
########################################
cat << 'EOF' > tests/fixtures/sample_csv_small.csv
cod;flag
1;S
2;N
EOF


########################################
# FILE: requirements.txt
########################################
cat << 'EOF' > requirements.txt
azure-functions
azure-storage-blob
pymongo
pandas
psutil

opentelemetry-api
opentelemetry-sdk
opentelemetry-exporter-otlp
opentelemetry-exporter-otlp-proto-grpc
opentelemetry-instrumentation-azure-functions
opentelemetry-instrumentation-requests
opentelemetry-instrumentation-pymongo
opentelemetry-instrumentation-azure-core

pytest
pytest-cov
EOF


########################################
# FILE: README.md
########################################
cat << 'EOF' > README.md
# Blob Ingestion - Azure Functions + MongoDB + OpenTelemetry

Este projeto implementa uma Azure Function que:
✅ Lê mensagem do Service Bus contendo a URL de um Blob CSV  
✅ Processa o arquivo em chunks com Pandas  
✅ Insere/upserta no MongoDB em paralelo  
✅ Exporta métricas e tracing com OpenTelemetry  

## Estrutura
- app/core: modelos e regras de negócio
- app/infra: leitura do blob e escrita no Mongo
- functions: Azure Function
- tests: testes unitários com pytest

## Rodando local