from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, List
from datetime import datetime

class FileType(Enum):
    DEFAULT_GROUP = "default_group"
    CUSTOMER_DATA = "customer_data" 

class FileExtension(Enum):
    CSV = "CSV"
    JSON = "JSON"

@dataclass
class BlobSettings:
    account_url: str
    account_key: str
    container_name: str
    input_path: str
    processed_path: str
    file_name: str

@dataclass
class MongoSettings:
    uri: str
    database: str
    collection: str

@dataclass
class FileSchema:
    name: str
    column_mapping: Dict[str, str]
    boolean_cols: List[str]
    key_fields: Optional[List[str]] = None
    file_type: FileExtension = FileExtension.CSV    
    sep: str = ";"

@dataclass
class IngestionSettings:
    schema: FileSchema
    mongo: MongoSettings
    blob: BlobSettings
    reference_date: str
    chunk_size: int = 50_000
    max_workers: int = 5
    encoding: str = "cp1252"