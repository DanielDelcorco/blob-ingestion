"""
Azure Functions app entry point.
Defines the HTTP-triggered processBlobEvent function.
"""
import json
from uuid import uuid4

import azure.functions as func
from azure.core import exceptions as azure_exceptions
from opentelemetry import trace, metrics

from app.config.logging_config import configure_logging, set_correlation_id
from app.config.otel_config import setup_otel
from app.config.ingestion_config import get_ingestion_settings
from app.core.models.ingestion_settings import FileType
from app.core.services.ingestion_service import IngestionService

# Initialize logging and OTEL
LOGGER = configure_logging()
tracer_provider, meter_provider, shutdown_otel = setup_otel(LOGGER)
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

ingested_counter = meter.create_counter(
    name="blob_files_ingested_total",
    unit="1",
    description="Total number of blob files ingested successfully"
)

# Create the main FunctionApp instance
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.function_name(name="processBlobEvent")
@app.route(route="process", methods=["POST"])
def processBlobEvent(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP trigger para processar arquivo CSV de um tipo específico.
    
    Request body:
    {
        "fileType": "default_group"  # Tipo do arquivo conforme configurado em file_types_config.py
    }
    """
    correlation_id = req.headers.get("X-Correlation-ID") or str(uuid4())
    set_correlation_id(correlation_id)
    
    with tracer.start_as_current_span("process_blob_event") as span:
        try:
            # Extrair tipo de arquivo do request
            span.set_attribute("correlation_id", correlation_id)
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

            # Support callers sending either a FileType enum (internal) or a string (external tests/HTTP).
            if isinstance(file_type, str):
                try:
                    file_type = FileType(file_type)
                except ValueError:
                    return func.HttpResponse(
                        json.dumps({"error": f"Tipo de arquivo '{file_type}' não suportado."}),
                        status_code=400,
                        mimetype="application/json",
                    )

            # Obter configuração do tipo de arquivo
            try:
                settings = get_ingestion_settings(file_type)
            except ValueError as e:
                LOGGER.error(f"event=invalid_file_type file_type={file_type} correlation_id={correlation_id}")
                return func.HttpResponse(
                    json.dumps({"error": str(e)}),
                    status_code=400,
                    mimetype="application/json"
                )

            LOGGER.info(f"event=processing_started file_type={file_type} correlation_id={correlation_id}")

            # create service and ensure cleanup
            service = IngestionService(settings, LOGGER)
            total_docs = 0
            try:
                span.set_attribute("file_type", file_type.value)
                total_docs = service.run()
            finally:
                try:
                    # service may implement close() to cleanup clients
                    service.close()
                except Exception:
                    LOGGER.debug("service.close() not available or failed", exc_info=True)

            # Record metric (do not include correlation_id as label — high cardinality)
            ingested_counter.add(
                total_docs,
                {"file_type": file_type.value}
            )

            span.set_attribute("docs_processed", total_docs)

            LOGGER.info(
                f"event=processing_completed file_type={file_type} total_docs={total_docs} correlation_id={correlation_id}"
            )

            return func.HttpResponse(
                json.dumps({
                    "status": "success",
                    "fileType": file_type.value,
                    "docsProcessed": total_docs,
                    "correlationId": correlation_id
                }),
                status_code=200,
                mimetype="application/json"
            )

        except Exception as e:
            # Map exceptions to structured responses
            def _map_exception_to_response(exc) -> tuple[int, str, str]:
                # returns (http_status, message, error_code)
                if isinstance(exc, azure_exceptions.ResourceNotFoundError):
                    return 404, "Blob container or blob not found", getattr(exc, "error_code", "ContainerNotFound")
                if isinstance(exc, azure_exceptions.ClientAuthenticationError):
                    return 401, "Blob authentication failed", getattr(exc, "error_code", "AuthenticationFailed")
                return 500, "Failed to process blob", "InternalError"

            status, msg, code = _map_exception_to_response(e)
            # attach error code to span and log concise message
            span.set_attribute("errorCode", code)
            LOGGER.error(
                "event=process_blob_event_failed correlation_id=%s error=%s errorCode=%s",
                correlation_id,
                msg,
                code,
                exc_info=False,
            )
            LOGGER.debug("full exception", exc_info=True)
            return func.HttpResponse(
                json.dumps({"error": msg, "errorCode": code, "correlationId": correlation_id}),
                status_code=status,
                mimetype="application/json"
            )
