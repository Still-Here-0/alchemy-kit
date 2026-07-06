from typing import Callable

from ..base_model import BaseModel


class ColumnUnit[_TypeParameters: str]:
    """A single column of a model, generic over the dialect's SQL type names
    (``_TypeParameters``, inferred from ``base``)."""

    def __init__(
        self,
        column_data: str,
        get_ref: Callable[[], str] | None,
        base: type[BaseModel[_TypeParameters]],
    ) -> None:
        self._data    = column_data
        self._get_ref = get_ref
        self._base    = base
        self._map     = base._map

        self._alias: str | None    = None
        self._cast: str | None     = None
        self._grouping: str | None = None

    def set_alias(self, alias: str):
        """Set the output name for this column."""
        self._alias = alias

    def cast(self, to: _TypeParameters):
        """Cast this column to a SQL type of the model's dialect."""
        self._cast = to

    def group(self, by: str):
        """Group this column by the given expression."""
        self._grouping = by
