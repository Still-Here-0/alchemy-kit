"""The per-dialect resources, for pinning a connection to its SQL type names.

Passing a map to ``ConnectionInfo``, ``from_env``, ``from_json`` or
``EngineManager.get_handler`` rejects a connection of another dialect and gives
every unit built from it a checked ``cast``.
"""

from .dialect_map import (
    MariadbMap,
    MssqlMap,
    MysqlMap,
    OracleMap,
    PostgresqlMap,
    SqliteMap,
)

__all__ = [
    "MariadbMap",
    "MssqlMap",
    "MysqlMap",
    "OracleMap",
    "PostgresqlMap",
    "SqliteMap",
]
