from .schema_model import SchemaModel



class DBModel:

    def __init__(self, name: str) -> None:
        self.name = name
        self.schemas: set[SchemaModel] = set()

    def add_schema(self, schema: SchemaModel):
        self.schemas.add(schema)
