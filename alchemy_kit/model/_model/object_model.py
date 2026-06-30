from .column_model import ColumnModel



class ObjectModel:

    def __init__(self, name: str) -> None:
        self.name = name
        self.columns: dict[str, ColumnModel] = {}
        self._unique_constrait: set[set[str]] = set()

    def add_unique_constrait(self, col_names: list[str]):
        keys = list(self.columns.keys())
        for col_name in col_names:
            if col_name not in keys:
                raise ValueError(f"Table '{self.name}' does not have a column called '{col_name}'")

        self._unique_constrait.add(set(col_names))

