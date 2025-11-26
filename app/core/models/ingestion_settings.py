from dataclasses import dataclass


@dataclass
class IngestionSettings:
    chunk_size: int = 50_000
    max_workers: int = 5
    encoding: str = "cp1252"
