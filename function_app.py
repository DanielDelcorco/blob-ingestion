"""
Azure Functions app entry point.
Defines the HTTP-triggered processBlobEvent function.
"""
import json
from datetime import datetime, UTC
from uuid import uuid4

import azure.functions as func
from opentelemetry import trace

from app.config.logging_config import configure_logging
from app.config.otel import setup_otel
from app.config.file_types_config import get_file_type_config
from app.config.blob_config import BlobClientFactory
from app.config.mongo_config import MongoClientFactory
from app.core.models.ingestion_settings import IngestionSettings
from app.core.services.ingestion_service import IngestionService
from app.infra.blob.blob_csv_reader import BlobCsvReader

# Initialize logging and OTEL
LOGGER = configure_logging()
tracer_provider, meter_provider, shutdown_otel = setup_otel(LOGGER)
tracer = trace.get_tracer(__name__)

# Create the main FunctionApp instance
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="process", methods=["POST"])
def processBlobEvent(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP trigger para processar arquivo CSV de um tipo específico.
    
    Request body:
    {
        "fileType": "default_group"  # Tipo do arquivo conforme configurado em file_types_config.py
    }
    """
    correlation_id = str(uuid4())
    
    with tracer.start_as_current_span("process_blob_event"):
        try:
            # Extrair tipo de arquivo do request
            try:
                req_json = req.get_json()
                file_type = req_json.get("fileType")
            except ValueError:
                return func.HttpResponse(
                    json.dumps({"error": "Invalid JSON in request body"}),
                    status_code=400,
                    mimetype="application/json"
                )

            if not file_type:
                return func.HttpResponse(
                    json.dumps({"error": "Missing 'fileType' in request body"}),
                    status_code=400,
                    mimetype="application/json"
                )

            # Obter configuração do tipo de arquivo
            try:
                file_config = get_file_type_config(file_type)
            except ValueError as e:
                LOGGER.error(f"event=invalid_file_type file_type={file_type} correlation_id={correlation_id}")
                return func.HttpResponse(
                    json.dumps({"error": str(e)}),
                    status_code=400,
                    mimetype="application/json"
                )

            LOGGER.info(f"event=processing_started file_type={file_type} correlation_id={correlation_id}")

            reference_date = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.000+00:00")

            # Criar BlobClient a partir do tipo de arquivo
            try:
                blob_client = BlobClientFactory.create(file_type)
            except ValueError as e:
                LOGGER.error(f"event=missing_blob_credentials correlation_id={correlation_id} error={str(e)}")
                return func.HttpResponse(
                    json.dumps({"error": str(e)}),
                    status_code=500,
                    mimetype="application/json"
                )

            # Configurações de ingestão
            settings = IngestionSettings()

            # Criar BlobClient e MongoWriter a partir do tipo de arquivo
            reader = BlobCsvReader(blob_client, file_config.schema, settings, LOGGER)
            writer = MongoClientFactory.create(file_type, LOGGER)
            # key_fields pode ser definido por tipo; passa None para manter default
            key_fields = getattr(file_config, "key_fields", None)
            service = IngestionService(reader, writer, settings, LOGGER, correlation_id, key_fields)

            total_docs = service.run()
            writer.delete_older_than(reference_date)
            writer.close()

            LOGGER.info(
                f"event=process_blob_event_success "
                f"file_type={file_type} "
                f"total_docs={total_docs} "
                f"correlation_id={correlation_id}"
            )

            return func.HttpResponse(
                json.dumps({
                    "status": "success",
                    "fileType": file_type,
                    "docsProcessed": total_docs,
                    "correlationId": correlation_id
                }),
                status_code=200,
                mimetype="application/json"
            )

        except Exception as e:
            LOGGER.exception(
                f"event=process_blob_event_failed "
                f"correlation_id={correlation_id} "
                f"error={str(e)}"
            )
            return func.HttpResponse(
                json.dumps({
                    "error": "Failed to process blob",
                    "correlationId": correlation_id
                }),
                status_code=500,
                mimetype="application/json"
            )
