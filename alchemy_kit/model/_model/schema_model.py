from .object_model import ObjectModel
from .procedure_model import ProcedureModel


class SchemaModel:

    def __init__(self, name: str) -> None:
        self.name = name
        self.objects: dict[str, ObjectModel] = {}
        self.callables: dict[str, ProcedureModel] = {}

