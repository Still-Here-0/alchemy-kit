from typing import Callable, NamedTuple

from sqlalchemy.dialects import mssql as sa_mssql
from sqlalchemy.dialects import mysql as sa_mysql
from sqlalchemy.dialects import oracle as sa_oracle
from sqlalchemy.dialects import postgresql as sa_postgresql
from sqlalchemy.dialects import sqlite as sa_sqlite
from sqlalchemy.dialects.mysql import mariadb as sa_mariadb
from sqlalchemy.engine import Dialect

from ...types.dialect_types import DialectTypes
from ...types.py_type_parameters import PyTypeParameters
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
    "get_sa_dialect",
    "get_str_length",
    "get_type",
    "render_reference",
    "render_type",
]

class _DialectEntry(NamedTuple):
    parameter_map: type[DialectMap]
    # Type objects (Literal, Union, ...) does not carry the variable name
    type_parameters: str
    sa_dialect: Callable[..., Dialect]


_REGISTRY: dict[DialectTypes, _DialectEntry] = {
    DialectTypes.MSSQL: _DialectEntry(MssqlMap, "MssqlTypeParameters", sa_mssql.dialect),
    DialectTypes.MYSQL: _DialectEntry(MysqlMap, "MysqlTypeParameters", sa_mysql.dialect),
    DialectTypes.MARIADB: _DialectEntry(MariadbMap, "MariadbTypeParameters", sa_mariadb.MariaDBDialect),
    DialectTypes.POSTGRESQL: _DialectEntry(PostgresqlMap, "PostgresqlTypeParameters", sa_postgresql.dialect),
    DialectTypes.ORACLE: _DialectEntry(OracleMap, "OracleTypeParameters", sa_oracle.dialect),
    DialectTypes.SQLITE: _DialectEntry(SqliteMap, "SqliteTypeParameters", sa_sqlite.dialect),
}


def get_map(dialect: DialectTypes) -> type[DialectMap]:
    """Return the resource class registered for ``dialect``."""
    try:
        return _REGISTRY[dialect].parameter_map
    except KeyError:
        raise ValueError(f"Dialect not mapped on dialect_map: {dialect}") from None


def get_sa_dialect(dialect: DialectTypes) -> Dialect:
    """Return a SQLAlchemy dialect instance for compiling Core statements.

    ``paramstyle="named"`` forces ``:param`` placeholders regardless of the
    DBAPI's default (e.g. ``qmark`` on pyodbc), which is what ``SQL`` /
    ``EngineHandler.run_sql`` expect. MariaDB gets its own dialect class so
    MariaDB-only types (``INET4``, ``INET6``, native ``uuid``) render.
    """
    try:
        return _REGISTRY[dialect].sa_dialect(paramstyle="named")
    except KeyError:
        raise ValueError(f"Dialect not mapped on dialect_map: {dialect}") from None


def get_codegen_imports(dialect: DialectTypes) -> tuple[str, str, str]:
    """Return the ``(map_module, map_class, type_parameters)`` identifiers a
    generated model needs to reference ``dialect``."""
    parameter_map = get_map(dialect)
    return parameter_map.__module__, parameter_map.__name__, _REGISTRY[dialect].type_parameters


def get_type(dialect: DialectTypes, sql_type: str) -> PyTypeParameters:
    """Map a raw SQL type name to its Python type name for ``dialect``."""
    return get_map(dialect).get_py_type(sql_type)


def render_type(dialect: DialectTypes, column: ColumnLike) -> str:
    """Render the fully-parameterised SQL type for ``column`` under ``dialect``."""
    return get_map(dialect).render_type(column)


def render_reference(dialect: DialectTypes, schema_name: str, object_name: str) -> str:
    """Render the fully-qualified, dialect-quoted reference for an object."""
    return get_map(dialect).render_reference(schema_name, object_name)


def get_str_length(dialect: DialectTypes, column: ColumnLike) -> int | None:
    """Return the max character length for a bounded string ``column``, else ``None``."""
    return get_map(dialect).str_length(column)

