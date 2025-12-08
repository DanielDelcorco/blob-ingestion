import os
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
    def create(file_type: str) -> BlobClient:
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
        # Obter configuração do tipo de arquivo
        file_config = get_file_type_config(file_type)

        # Obter credenciais
        account_name = os.getenv("AZURE_BLOB_ACCOUNT_NAME")
        sas_token = os.getenv("AZURE_BLOB_SAS_TOKEN")

        if not account_name or not sas_token:
            raise ValueError("Azure Blob Storage credentials not configured (AZURE_BLOB_ACCOUNT_NAME or AZURE_BLOB_SAS_TOKEN)")

        # Construir URL do blob
        blob_url = f"https://{account_name}.blob.core.windows.net/{file_config.blob_container}/{file_config.blob_path}?{sas_token}"

        # Criar e retornar BlobClient
        return BlobClient.from_blob_url(blob_url)
