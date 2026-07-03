from ..._core.types.dialect_types import DialectTypes
from .schema_model import SchemaModel


class DBModel:

    def __init__(self, name: str | None, dialect: DialectTypes) -> None:
        self.name = name
        self.dialect: DialectTypes = dialect
        self.schemas: dict[str, SchemaModel] = {}

