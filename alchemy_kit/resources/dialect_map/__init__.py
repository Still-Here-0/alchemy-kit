from typing import Any, Literal, overload

from ...types.dialect_types import DialectTypesInput
from ._base import ColumnLike, DialectMap, ReflectedTypeFacts
from .mariadb import MariadbMap
from .mssql import MssqlMap
from .mysql import MysqlMap
from .oracle import OracleMap
from .postgresql import PostgresqlMap
from .sqlite import SqliteMap

__all__ = [
    "DIALECT_MAPS",
    "ColumnLike",
    "DialectLike",
    "DialectMap",
    "MariadbMap",
    "MssqlMap",
    "MysqlMap",
    "OracleMap",
    "PostgresqlMap",
    "ReflectedTypeFacts",
    "SqliteMap",
    "get_map",
    "resolve_map",
]

DIALECT_MAPS: tuple[type[DialectMap[Any]], ...] = (
    MssqlMap,
    MysqlMap,
    MariadbMap,
    PostgresqlMap,
    OracleMap,
    SqliteMap,
)

_REGISTRY: dict[str, type[DialectMap[Any]]] = {
    dialect_map.name: dialect_map for dialect_map in DIALECT_MAPS
}


type DialectLike = DialectTypesInput | type[DialectMap[Any]]


def resolve_map(dialect: DialectLike) -> type[DialectMap[Any]]:
    """Return the map for either form a caller may pass — the dialect's name or
    the map itself."""
    return get_map(dialect) if isinstance(dialect, str) else dialect


@overload
def get_map(name: Literal["mssql"]) -> type[MssqlMap]: ...
@overload
def get_map(name: Literal["mysql"]) -> type[MysqlMap]: ...
@overload
def get_map(name: Literal["mariadb"]) -> type[MariadbMap]: ...
@overload
def get_map(name: Literal["postgresql"]) -> type[PostgresqlMap]: ...
@overload
def get_map(name: Literal["oracle"]) -> type[OracleMap]: ...
@overload
def get_map(name: Literal["sqlite"]) -> type[SqliteMap]: ...
@overload
def get_map(name: str) -> type[DialectMap[Any]]: ...
def get_map(name: str) -> type[DialectMap[Any]]:
    """Return the map registered under a dialect's name.

    Overloaded per name, so a literal keeps the dialect's SQL type names:
    ``get_map("mssql")`` is a ``type[MssqlMap]``.

    Raises:
        ValueError: If no dialect is registered under ``name``.
    """
    try:
        return _REGISTRY[name]
    except KeyError:
        raise ValueError(f"Dialect not mapped on dialect_map: {name}") from None
