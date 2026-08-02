from typing import Any
from .schema_model import SchemaModel
from ...resources.dialect_map import DialectMap


class DBModel:

    def __init__(self, name: str | None, dialect: type[DialectMap[Any]]) -> None:
        self.name = name
        self.dialect: type[DialectMap[Any]] = dialect
        self.schemas: dict[str, SchemaModel] = {}

