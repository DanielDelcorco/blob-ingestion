import json
import os
from datetime import datetime, UTC

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

        reference_date = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.000+00:00")

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
