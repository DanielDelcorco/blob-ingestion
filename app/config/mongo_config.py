import os
from app.config.file_types_config import get_file_type_config
from app.core.models.mongo_settings import MongoSettings
from app.infra.mongo.mongo_writer import MongoWriter


class MongoClientFactory:
    """Factory para resolver e construir MongoWriter a partir do tipo de arquivo.
    
    Encapsula:
    - Resolução de configurações de MongoDB (URI, database, collection) por tipo
    - Leitura de credenciais e overrides de ambiente
    - Instanciação do MongoWriter
    """

    @staticmethod
    def create(file_type: str, logger) -> MongoWriter:
        """
        Cria um MongoWriter a partir do tipo de arquivo.

        Args:
            file_type: Tipo do arquivo conforme configurado em file_types_config.py
            logger: Logger instance para passar ao MongoWriter

        Returns:
            MongoWriter pronto para usar

        Raises:
            ValueError: Se tipo de arquivo não existir
        """
        # Obter configuração do tipo de arquivo
        file_config = get_file_type_config(file_type)

        # Obter configurações do MongoDB (collection pode ser overriden pela config do tipo)
        mongo_collection = file_config.mongo_collection or os.getenv("MONGO_COLLECTION_NAME", "defaultGroupDocument")
        
        mongo_settings = MongoSettings(
            uri=os.getenv("MONGO_URI", "mongodb://localhost:27017"),
            database=os.getenv("MONGO_DB_NAME", "slp"),
            collection=mongo_collection,
        )

        # Criar e retornar MongoWriter
        return MongoWriter(mongo_settings, logger)
