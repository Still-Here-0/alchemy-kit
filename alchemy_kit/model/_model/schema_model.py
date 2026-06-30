from .object_model import ObjectModel



class SchemaModel:

    def __init__(self, name: str) -> None:
        self.name = name
        self.objects: dict[str, ObjectModel] = {}

