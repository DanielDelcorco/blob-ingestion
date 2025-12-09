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

        if not account_name or not sas_token:
            raise ValueError("Azure Blob Storage credentials not configured (AZURE_BLOB_ACCOUNT_NAME or AZURE_BLOB_SAS_TOKEN)")

        # Normalizar token e blob path para evitar caracteres inválidos
        sas_token = sas_token.strip()
        if sas_token.startswith("?"):
            sas_token = sas_token[1:]

        blob_name = getattr(file_config, "blob_path", "") or ""
        blob_name = blob_name.lstrip("/")

        account_url = f"https://{account_name}.blob.core.windows.net"

        logger = logging.getLogger(__name__)
        logger.debug(
            "Creating BlobClient account_url=%s container=%s blob=%s sas_len=%d",
            account_url,
            file_config.blob_container,
            blob_name,
            len(sas_token),
        )

        # Use the credential parameter instead of constructing a URL string.
        try:
            client = BlobClient(
                account_url=account_url,
                container_name=file_config.blob_container,
                blob_name=blob_name,
                credential=sas_token,
            )
        except Exception:
            logger.exception("Failed to construct BlobClient")
            raise

        return client
