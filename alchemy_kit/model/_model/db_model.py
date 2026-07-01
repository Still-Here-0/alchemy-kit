from .schema_model import SchemaModel



class DBModel:

    def __init__(self, name: str | None) -> None:
        self.name = name
        self.schemas: dict[str, SchemaModel] = {}

