import os
import logging
from azure.storage.blob import BlobClient
from app.config.file_types_config import get_file_type_config


class BlobClientFactory:
    """Factory para resolver e construir BlobClient a partir do tipo de arquivo.
    
    Encapsula:
    - Resolução de configurações de blob (container, path) por tipo
    - Leitura de credenciais (account name, SAS token)
    - Construção da URL do blob
    - Instanciação do BlobClient
    """

    @staticmethod
    def create(file_type_or_config) -> BlobClient:
        """
        Cria um BlobClient a partir do tipo de arquivo.

        Args:
            file_type: Tipo do arquivo conforme configurado em file_types_config.py

        Returns:
            BlobClient pronto para usar

        Raises:
            ValueError: Se credenciais do Azure Blob não estiverem configuradas
            ValueError: Se tipo de arquivo não existir
        """
        # Aceita tanto o objeto FileTypeConfig quanto o identificador string
        if isinstance(file_type_or_config, str):
            file_config = get_file_type_config(file_type_or_config)
        else:
            file_config = file_type_or_config

        # Obter credenciais
        account_name = os.getenv("AZURE_BLOB_ACCOUNT_NAME")
        sas_token = os.getenv("AZURE_BLOB_SAS_TOKEN")

        if not sas_token:
            raise ValueError("Azure Blob Storage SAS token not configured (AZURE_BLOB_SAS_TOKEN)")

        # Prefer connection string (AzureWebJobsStorage or explicit) for local Azurite
        conn_str = os.getenv("AZURE_BLOB_CONNECTION_STRING") or os.getenv("AzureWebJobsStorage")
        blob_name = getattr(file_config, "blob_path", "") or ""
        blob_name = blob_name.lstrip("/")

        logger = logging.getLogger(__name__)

        if conn_str:
            # Use connection string flow (good for Azurite / local development)
            logger.debug("Creating BlobClient from connection string, container=%s blob=%s", file_config.blob_container, blob_name)
            try:
                client = BlobClient.from_connection_string(conn_str, container_name=file_config.blob_container, blob_name=blob_name)
            except Exception:
                logger.exception("Failed to construct BlobClient from connection string")
                raise
            return client

        # Fallback: use SAS token + base URL
        # Normalizar token
        sas_token = sas_token.strip()
        if sas_token.startswith("?"):
            sas_token = sas_token[1:]

        # Obter base URL do Blob via variável de ambiente (preferível)
        base_blob_url = os.getenv("AZURE_BLOB_URL")
        if base_blob_url:
            base_blob_url = base_blob_url.rstrip("/")
        elif account_name:
            base_blob_url = f"https://{account_name}.blob.core.windows.net"
        else:
            raise ValueError("Azure Blob Storage base URL not configured (AZURE_BLOB_URL or AZURE_BLOB_ACCOUNT_NAME)")

        logger.debug(
            "Creating BlobClient base_url=%s container=%s blob=%s sas_len=%d",
            base_blob_url,
            file_config.blob_container,
            blob_name,
            len(sas_token),
        )

        # Use the credential parameter instead of constructing a URL string.
        try:
            client = BlobClient(
                account_url=base_blob_url,
                container_name=file_config.blob_container,
                blob_name=blob_name,
                credential=sas_token,
            )
        except Exception:
            logger.exception("Failed to construct BlobClient")
            raise

        return client
