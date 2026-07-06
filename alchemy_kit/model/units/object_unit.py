from ..base_model import BaseModel, MetaData
from .column_unit import ColumnUnit


class ObjectUnit[_TypeParameters: str]:
    """A selectable database object (table/view) from a generated model, generic
    over the dialect's SQL type names (``_TypeParameters``, inferred from
    ``base``)."""

    def __init__(self, base: type[BaseModel[_TypeParameters]]) -> None:
        self._base = base

        self._object_name = self.get_metadata()["obj_name"]

        self._alias: str | None = None

    def __getattr__(self, name: str) -> ColumnUnit[_TypeParameters]:
        if name.startswith("_"):
            raise AttributeError(name)
        return ColumnUnit(name, self.get_reference, self._base)

    def set_alias(self, alias: str):
        """Set the alias used to qualify this object's columns."""
        self._alias = alias

    def get_metadata(self) -> MetaData:
        """Return the table `MetaData` recorded on the model by the builder."""
        return self._base.Config.metadata

    def get_reference(self) -> str:
        """Return the alias when set, else the object's name."""
        return self._alias if self._alias is not None else self._object_name

