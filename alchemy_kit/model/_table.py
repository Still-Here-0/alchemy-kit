from typing import Any

import sqlalchemy as sa

from ..resources.dialect_map import DialectMap, get_map
from ..types.dialect_types import DialectTypes
from ._builders._column_metadata import ColumnMetadata
from .base_model import BaseModel

_TABLES: dict[tuple[type[BaseModel], DialectTypes], sa.Table] = {}


def _column_from_model(name: str, column: Any, dialect_map: type[DialectMap[Any]]) -> sa.Column[Any]:
    metadata = ColumnMetadata.from_dict(column.metadata)
    sa_type = dialect_map.get_sa_type(
        metadata.original_type, metadata.precision, metadata.scale
    )

    return sa.Column(
        name,
        sa_type,
        nullable=bool(column.nullable),
        primary_key=metadata.primary_key,
    )


def table_from_model(base: type[BaseModel], dialect: DialectTypes) -> sa.Table:
    """Return the SQLAlchemy Core ``Table`` for a generated model, built in
    memory from the model's metadata (no reflection) and cached per
    ``(model, dialect)``.

    Columns carry the dialect's SQLAlchemy type (parameterised with the
    recorded precision/scale for numerics), nullability, and primary-key
    flags, so the table serves both expression compilation and DDL rendering.
    """
    if (base, dialect) not in _TABLES:
        metadata = base.Config.metadata
        dialect_map = get_map(dialect)
        _TABLES[base, dialect] = sa.Table(
            metadata["obj_name"],
            sa.MetaData(),
            *(
                _column_from_model(str(name), column, dialect_map)
                for name, column in base.to_schema().columns.items()
            ),
            schema=metadata["schema_name"],
        )
    return _TABLES[base, dialect]


def clone_table(source: sa.Table, name: str, prefixes: list[str]) -> sa.Table:
    """Return a new ``Table`` named ``name`` cloning ``source``'s columns, with
    the given DDL ``prefixes`` (e.g. ``TEMPORARY``)."""
    return sa.Table(
        name,
        sa.MetaData(),
        *(
            sa.Column(c.name, c.type, nullable=c.nullable, primary_key=c.primary_key)
            for c in source.columns
        ),
        prefixes=prefixes,
    )
