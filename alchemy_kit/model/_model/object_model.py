from .column_model import ColumnModel
from .constraint_model import CheckConstraintModel, FilteredUniqueIndexModel, ForeignKeyConstraintModel
from ...types._sql_utilities import ObjectType


class ObjectModel:

    def __init__(self, obj_name: str, obj_type: ObjectType, description: str | None) -> None:
        self.name = obj_name
        self.type = obj_type
        self.description = description
        self.columns: dict[str, ColumnModel] = {}
        self._unique_constrait: set[frozenset[str]] = set()
        self.foreign_keys: dict[str, ForeignKeyConstraintModel] = {}
        self.check_constraints: dict[str, CheckConstraintModel] = {}
        self.filtered_unique_indexes: dict[str, FilteredUniqueIndexModel] = {}

    def add_unique_constrait(self, col_names: list[str]):
        keys = list(self.columns.keys())
        for col_name in col_names:
            if col_name not in keys:
                raise ValueError(f"Table '{self.name}' does not have a column called '{col_name}'")

        self._unique_constrait.add(frozenset(col_names))

    def get_unique_constrait(self) -> list[list[str]] | None:
        if not self._unique_constrait:
            return None
        
        return [list(uq) for uq in self._unique_constrait]

