from .object_model import ObjectModel



class SchemaModel:

    def __init__(self, name: str) -> None:
        self.name = name
        self.objects: set[ObjectModel] = set()

    def add_object(self, obj: ObjectModel):
        self.objects.add(obj)
