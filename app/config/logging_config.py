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
