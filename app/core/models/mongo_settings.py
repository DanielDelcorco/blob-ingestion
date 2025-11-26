from dataclasses import dataclass


@dataclass
class MongoSettings:
    uri: str
    database: str
    collection: str
