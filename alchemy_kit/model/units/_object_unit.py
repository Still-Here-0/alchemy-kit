from typing import TYPE_CHECKING

from sqlalchemy.sql.expression import FromClause

from ..base_model import BaseModel, MetaData
from .._table import table_from_model
from ._column_unit import ColumnUnit

if TYPE_CHECKING:
    from ...connect._engine_handler import EngineHandler


class ObjectUnit[_TypeParameters: str]:
    """A selectable database object (table/view) from a generated model,
    wrapping the SQLAlchemy Core ``Table`` built from the model's metadata
    with the handler's connection dialect. Generic over the dialect's SQL
    type names (``_TypeParameters``, inferred from ``base``).

    Attribute access yields :class:`ColumnUnit` instances wrapping the
    underlying Core columns; the model's Python field names resolve to their
    SQL column names automatically.
    """

    def __init__(
        self,
        base: type[BaseModel[_TypeParameters]],
        handler: "EngineHandler",
        selectable: FromClause | None = None,
    ) -> None:
        self._base = base
        self._handler = handler
        self._selectable = (
            table_from_model(base, handler._con_info.dialect)
            if selectable is None
            else selectable
        )

    def __getattr__(self, name: str) -> ColumnUnit[_TypeParameters]:
        if name.startswith("_"):
            raise AttributeError(name)

        sql_name = getattr(self._base, name, name)
        if not isinstance(sql_name, str):
            sql_name = name

        try:
            column = self._selectable.c[sql_name]
        except KeyError:
            raise AttributeError(name) from None

        return ColumnUnit(column, self._base, self._handler)

    def set_alias(self, alias: str) -> "ObjectUnit[_TypeParameters]":
        """Return a new unit selecting from this object aliased as ``alias``;
        its columns carry the alias into every reference."""
        return ObjectUnit(self._base, self._handler, self._selectable.alias(alias))

    def get_metadata(self) -> MetaData:
        """Return the table `MetaData` recorded on the model by the builder."""
        return self._base.Config.metadata

