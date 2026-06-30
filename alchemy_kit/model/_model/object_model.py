from .column_model import ColumnModel



class ObjectModel:

    def __init__(self, name: str) -> None:
        self.name = name
        self.columns: set[ColumnModel] = set()
        self.unique_constrait: set[set[ColumnModel]] = set()

    def add_column(self, column: ColumnModel):
        self.columns.add(column)

    def add_unique_constrait(self, column_names: list[str]):
        ...
