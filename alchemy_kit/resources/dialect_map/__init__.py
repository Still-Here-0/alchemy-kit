from typing import NamedTuple

from ...types.dialect_types import DialectTypes
from ._base import ColumnLike, DialectMap, ReflectedTypeFacts
from .mariadb import MariadbMap
from .mssql import MssqlMap
from .mysql import MysqlMap
from .oracle import OracleMap
from .postgresql import PostgresqlMap
from .sqlite import SqliteMap

__all__ = [
    "ColumnLike",
    "DialectMap",
    "ReflectedTypeFacts",
    "get_codegen_imports",
    "get_map",
    "get_str_length",
    "get_type",
    "render_type",
]

class _DialectEntry(NamedTuple):
    parameter_map: type[DialectMap]
    # Type objects (Literal, Union, ...) does not carry the variable name
    type_parameters: str


_REGISTRY: dict[DialectTypes, _DialectEntry] = {
    DialectTypes.MSSQL: _DialectEntry(MssqlMap, "MssqlTypeParameters"),
    DialectTypes.MYSQL: _DialectEntry(MysqlMap, "MysqlTypeParameters"),
    DialectTypes.MARIADB: _DialectEntry(MariadbMap, "MariadbTypeParameters"),
    DialectTypes.POSTGRESQL: _DialectEntry(PostgresqlMap, "PostgresqlTypeParameters"),
    DialectTypes.ORACLE: _DialectEntry(OracleMap, "OracleTypeParameters"),
    DialectTypes.SQLITE: _DialectEntry(SqliteMap, "SqliteTypeParameters"),
}


def get_map(dialect: DialectTypes) -> type[DialectMap]:
    """Return the resource class registered for ``dialect``."""
    try:
        return _REGISTRY[dialect].parameter_map
    except KeyError:
        raise ValueError(f"Dialect not mapped on dialect_map: {dialect}") from None


def get_codegen_imports(dialect: DialectTypes) -> tuple[str, str, str]:
    """Return the ``(map_module, map_class, type_parameters)`` identifiers a
    generated model needs to reference ``dialect``."""
    parameter_map = get_map(dialect)
    return parameter_map.__module__, parameter_map.__name__, _REGISTRY[dialect].type_parameters


def get_type(dialect: DialectTypes, sql_type: str) -> str:
    """Map a raw SQL type name to its Python type name for ``dialect``."""
    return get_map(dialect).get_py_type(sql_type)


def render_type(dialect: DialectTypes, column: ColumnLike) -> str:
    """Render the fully-parameterised SQL type for ``column`` under ``dialect``."""
    return get_map(dialect).render_type(column)


def get_str_length(dialect: DialectTypes, column: ColumnLike) -> int | None:
    """Return the max character length for a bounded string ``column``, else ``None``."""
    return get_map(dialect).str_length(column)

