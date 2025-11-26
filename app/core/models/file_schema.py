from dataclasses import dataclass
from typing import Dict, List


@dataclass
class FileSchema:
    name: str
    column_mapping: Dict[str, str]
    boolean_cols: List[str]
