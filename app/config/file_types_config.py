from dataclasses import dataclass
from typing import Dict, List, Optional
import os
from app.core.models.file_schema import FileSchema


@dataclass
class FileTypeConfig:
    """Configuração de um tipo de arquivo suportado.

    Fields:
    - name: identificador do tipo
    - blob_container: nome do container
    - blob_path: caminho estático do blob (padrão)
    - schema: mapeamento de colunas e booleanos
    - key_fields: chaves usadas para upsert (opcional, usa default se não setado)
    - mongo_collection: collection override para esse tipo (opcional)
    """
    name: str
    blob_container: str
    blob_path: str
    schema: FileSchema
    key_fields: Optional[List[str]] = None
    mongo_collection: Optional[str] = None


# Mapeamento de tipos de arquivo para suas configurações
FILE_TYPES_CONFIG: Dict[str, FileTypeConfig] = {
    "default_group": FileTypeConfig(
        name="default_group",
        blob_container=os.getenv("DEFAULT_GROUP_BLOB_CONTAINER", "blob-container"),
        blob_path="default_group.csv",
        schema=FileSchema(
            name="default_group",
            column_mapping={
                "cod_grupo_limite_posicao": "defaultGroupId",
                "nome_grupo_limite_posicao": "defaultGroupName",
                "cod_cobranca_automatica": "automaticMarginCall",
                "num_documento_integrante": "documentId",
            },
            boolean_cols=["automaticMarginCall"],
        ),
        key_fields=["defaultGroupId", "documentId"],
        mongo_collection=os.getenv("DEFAULT_GROUP_MONGO_COLLECTION"),
    ),
    "customer_data": FileTypeConfig(
        name="customer_data",
        blob_container=os.getenv("CUSTOMER_BLOB_CONTAINER", "customer-container"),
        blob_path="customer_data.csv",
        schema=FileSchema(
            name="customer_data",
            column_mapping={
                "id_cliente": "customerId",
                "nome": "name",
                "email": "email",
                "assinante": "subscribed",
            },
            boolean_cols=["subscribed"],
        ),
        key_fields=["customerId"],
        mongo_collection=os.getenv("CUSTOMER_MONGO_COLLECTION", "customerCollection"),
    ),
}


def get_file_type_config(file_type: str) -> FileTypeConfig:
    """
    Obtém a configuração de um tipo de arquivo.

    Raises ValueError se não existir.
    """
    if file_type not in FILE_TYPES_CONFIG:
        available = list(FILE_TYPES_CONFIG.keys())
        raise ValueError(
            f"Tipo de arquivo '{file_type}' não suportado. Tipos disponíveis: {', '.join(available)}"
        )
    file_config = FILE_TYPES_CONFIG[file_type]
    # Validate configured key_fields against schema mapping before returning
    if getattr(file_config, "key_fields", None):
        mapped_fields = set(file_config.schema.column_mapping.values())
        missing = [k for k in file_config.key_fields if k not in mapped_fields]
        if missing:
            raise ValueError(
                f"Invalid key_fields for '{file_type}': {missing}."
                f" Keys must match target field names defined in schema.column_mapping ({sorted(mapped_fields)})"
            )

    return file_config
