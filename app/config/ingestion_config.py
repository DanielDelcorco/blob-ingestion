from dataclasses import dataclass
import datetime
from typing import Dict, List, Optional
import os

from app.core.models.ingestion_settings import BlobSettings, FileSchema, FileType, IngestionSettings, MongoSettings

# Mapeamento de tipos de arquivo para suas configurações
FILE_TYPES_CONFIG: Dict[FileType, IngestionSettings] = {
    FileType.DEFAULT_GROUP: IngestionSettings(
        # reference_date should reflect execution minute (seconds fixed to 00)
        reference_date=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:00.000+00:00"),
        schema=FileSchema(
            name="default_group",
            column_mapping={
                "cod_grupo_limite_posicao": "defaultGroupId",
                "nome_grupo_limite_posicao": "defaultGroupName",
                "cod_cobranca_automatica": "automaticMarginCall",
                "num_documento_integrante": "documentId",
            },
            boolean_cols=["automaticMarginCall"],
            key_fields=["defaultGroupId", "documentId"]
        ),
        mongo=MongoSettings(
            uri=os.getenv("MONGO_URI", "mongodb://localhost:27017"),
            database=os.getenv("MONGO_DB_NAME", "slp"),
            collection=os.getenv("DEFAULT_GROUP_MONGO_COLLECTION", "defaultGroupDocument"),
        ),
        blob=BlobSettings(
            account_url=os.getenv("BLOB_ACCOUNT_URL", "http://localhost:10000/"),
            account_key=os.getenv("BLOB_ACCOUNT_KEY", "˜EbQ#rX8Z2Vj!5JH7^2"),
            container_name=os.getenv("DEFAULT_GROUP_BLOB_CONTAINER", "devstoreaccount1"),
            input_path="input/",
            processed_path=os.getenv("DEFAULT_GROUP_PROCESSED_PATH", "processed/"),
            file_name="default_group.csv",
        )
    ),
    FileType.CUSTOMER_DATA: IngestionSettings(
        # reference_date should reflect execution minute (seconds fixed to 00)
        reference_date=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:00.000+00:00"),
        schema=FileSchema(
            name="default_group",
            column_mapping={
                "cod_grupo_limite_posicao": "defaultGroupId",
                "nome_grupo_limite_posicao": "defaultGroupName",
                "cod_cobranca_automatica": "automaticMarginCall",
                "num_documento_integrante": "documentId",
            },
            boolean_cols=["automaticMarginCall"],
            key_fields=["defaultGroupId", "documentId"]
        ),
        mongo=MongoSettings(
            uri=os.getenv("MONGO_URI", "mongodb://localhost:27017"),
            database=os.getenv("MONGO_DB_NAME", "slp"),
            collection=os.getenv("DEFAULT_GROUP_MONGO_COLLECTION", "defaultGroupDocument"),
        ),
        blob=BlobSettings(
            account_url=os.getenv("BLOB_ACCOUNT_URL", "http://localhost:10000/"),
            account_key=os.getenv("BLOB_ACCOUNT_KEY", "˜EbQ#rX8Z2Vj!5JH7^2"),
            container_name=os.getenv("DEFAULT_GROUP_BLOB_CONTAINER", "devstoreaccount1"),
            input_path="input/",
            processed_path=os.getenv("DEFAULT_GROUP_PROCESSED_PATH", "processed/"),
            file_name="default_group.csv",
        )
    )
}


def get_ingestion_settings(file_type: FileType) -> IngestionSettings:
    if file_type not in FILE_TYPES_CONFIG:
        available = list(FILE_TYPES_CONFIG.keys())
        raise ValueError(
            f"Tipo de arquivo '{file_type}' não suportado. Tipos disponíveis: {', '.join(available)}"
        )
    settings = FILE_TYPES_CONFIG[file_type]
    # Validate configured key_fields against schema mapping before returning
    if getattr(settings.schema, "key_fields", None):
        mapped_fields = set(settings.schema.column_mapping.values())
        missing = [k for k in settings.schema.key_fields if k not in mapped_fields]
        if missing:
            raise ValueError(
                f"Invalid key_fields for '{file_type}': {missing}."
                f" Keys must match target field names defined in schema.column_mapping ({sorted(mapped_fields)})"
            )

    return settings
