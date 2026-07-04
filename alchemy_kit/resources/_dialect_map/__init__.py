from ...types.dialect_types import DialectTypes
from ._base import ColumnLike, DialectParameterMap
from .mssql import MssqlParameterMap, MssqlTypeParameters

_REGISTRY: dict[DialectTypes, type[DialectParameterMap]] = {
    DialectTypes.MSSQL: MssqlParameterMap,
}


def get_map(dialect: DialectTypes) -> type[DialectParameterMap]:
    """Return the resource class registered for ``dialect``."""
    try:
        return _REGISTRY[dialect]
    except KeyError:
        raise ValueError(f"Dialect not mapped on dialect_map: {dialect}") from None


def get_type(dialect: DialectTypes, sql_type: str) -> str:
    """Map a raw SQL type name to its Python type name for ``dialect``."""
    return get_map(dialect).get_py_type(sql_type)


def render_type(dialect: DialectTypes, column: ColumnLike) -> str:
    """Render the fully-parameterised SQL type for ``column`` under ``dialect``."""
    return get_map(dialect).render_type(column)


def get_str_length(dialect: DialectTypes, column: ColumnLike) -> int | None:
    """Return the max character length for a bounded string ``column``, else ``None``."""
    return get_map(dialect).str_length(column)


__all__ = [
    "ColumnLike",
    "DialectParameterMap",
    "MssqlTypeParameters",
    "get_map",
    "get_str_length",
    "get_type",
    "render_type",
]
