from typing import Any

import sqlalchemy as sa
from sqlalchemy.sql.expression import FromClause

from ..base_model import BaseModel, MetaData
from .._builders._column_metadata import ColumnMetadata
from ._column_unit import ColumnUnit

_TABLES: dict[type[BaseModel[Any]], sa.Table] = {}


def _column_from_model(name: str, column: Any, base: type[BaseModel[Any]]) -> sa.Column[Any]:
    metadata = ColumnMetadata.from_dict(column.metadata)
    sa_type = base._map.get_sa_type(metadata.original_type)

    if isinstance(sa_type, sa.Numeric):
        if metadata.precision:
            sa_type.precision = metadata.precision
        if metadata.scale:
            sa_type.scale = metadata.scale

    return sa.Column(
        name,
        sa_type,
        nullable=bool(column.nullable),
        primary_key=metadata.primary_key,
    )


def table_from_model(base: type[BaseModel[Any]]) -> sa.Table:
    """Return the SQLAlchemy Core ``Table`` for a generated model, built in
    memory from the model's metadata (no reflection) and cached per model.

    Columns carry the dialect's SQLAlchemy type (parameterised with the
    recorded precision/scale for numerics), nullability, and primary-key
    flags, so the table serves both expression compilation and DDL rendering.
    """
    if base not in _TABLES:
        metadata = base.Config.metadata
        _TABLES[base] = sa.Table(
            metadata["obj_name"],
            sa.MetaData(),
            *(
                _column_from_model(str(name), column, base)
                for name, column in base.to_schema().columns.items()
            ),
            schema=metadata["schema_name"],
        )
    return _TABLES[base]


class ObjectUnit[_TypeParameters: str]:
    """A selectable database object (table/view) from a generated model,
    wrapping the SQLAlchemy Core ``Table`` built from the model's metadata.
    Generic over the dialect's SQL type names (``_TypeParameters``, inferred
    from ``base``).

    Attribute access yields :class:`ColumnUnit` instances wrapping the
    underlying Core columns; the model's Python field names resolve to their
    SQL column names automatically.
    """

    def __init__(
        self,
        base: type[BaseModel[_TypeParameters]],
        selectable: FromClause | None = None,
    ) -> None:
        self._base = base
        self._selectable = table_from_model(base) if selectable is None else selectable

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

        return ColumnUnit(column, self._base)

    def set_alias(self, alias: str) -> "ObjectUnit[_TypeParameters]":
        """Return a new unit selecting from this object aliased as ``alias``;
        its columns carry the alias into every reference."""
        return ObjectUnit(self._base, self._selectable.alias(alias))

    def get_metadata(self) -> MetaData:
        """Return the table `MetaData` recorded on the model by the builder."""
        return self._base.Config.metadata

