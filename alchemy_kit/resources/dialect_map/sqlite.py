from typing import cast, get_args

from alchemy_kit.types.dialect_types import DialectTypes

from sqlalchemy.dialects import sqlite as sa_sqlite
from sqlalchemy.types import BIGINT, CLOB, DOUBLE, DOUBLE_PRECISION, NCHAR, NVARCHAR, SMALLINT

from ._base import ColumnLike, DialectMap, ReflectedTypeFacts, SaTypeFactory
from ...types.py_type_parameters import PyTypeParameters
from ...types.sql_type_parameters import SqliteTypeParameters


class SqliteMap(DialectMap[SqliteTypeParameters]):

    _PY_TYPES: dict[SqliteTypeParameters, PyTypeParameters] = {
        # INTEGER affinity
        "int": "int",
        "integer": "int",
        "tinyint": "int",
        "smallint": "int",
        "mediumint": "int",
        "bigint": "int",
        "unsigned big int": "int",
        "int2": "int",
        "int8": "int",
        # REAL affinity
        "real": "float",
        "double": "float",
        "double precision": "float",
        "float": "float",
        # NUMERIC affinity (Decimal is not imported by the template, so use float)
        "numeric": "float",
        "decimal": "float",
        "boolean": "bool",
        "date": "date",
        "datetime": "datetime",
        # TEXT affinity
        "character": "str",
        "varchar": "str",
        "varying character": "str",
        "nchar": "str",
        "native character": "str",
        "nvarchar": "str",
        "text": "str",
        "clob": "str",
        # BLOB affinity
        "blob": "Any",
    }

    _SA_TYPES: dict[SqliteTypeParameters, SaTypeFactory] = {
        # INTEGER affinity
        "int": sa_sqlite.INTEGER,
        "integer": sa_sqlite.INTEGER,
        "tinyint": SMALLINT,
        "smallint": sa_sqlite.SMALLINT,
        "mediumint": sa_sqlite.INTEGER,
        "bigint": BIGINT,
        "unsigned big int": BIGINT,
        "int2": SMALLINT,
        "int8": BIGINT,
        # REAL affinity
        "real": sa_sqlite.REAL,
        "double": DOUBLE,
        "double precision": DOUBLE_PRECISION,
        "float": sa_sqlite.FLOAT,
        # NUMERIC affinity
        "numeric": sa_sqlite.NUMERIC,
        "decimal": sa_sqlite.DECIMAL,
        "boolean": sa_sqlite.BOOLEAN,
        "date": sa_sqlite.DATE,
        "datetime": sa_sqlite.DATETIME,
        # TEXT affinity
        "character": sa_sqlite.CHAR,
        "varchar": sa_sqlite.VARCHAR,
        "varying character": sa_sqlite.VARCHAR,
        "nchar": NCHAR,
        "native character": NCHAR,
        "nvarchar": NVARCHAR,
        "text": sa_sqlite.TEXT,
        "clob": CLOB,
        # BLOB affinity
        "blob": sa_sqlite.BLOB,
    }

    # SQL type name buckets (SQLite ignores length constraints, but declared
    # lengths are preserved for rendering and validation)
    _length_types_char: set[SqliteTypeParameters] = {
        "character", "varchar", "varying character",
        "nchar", "native character", "nvarchar",
    }
    _numerical_parametise: set[SqliteTypeParameters] = {"decimal", "numeric"}

    # Parent parameters
    py_types = cast(dict[str, PyTypeParameters], _PY_TYPES)
    sa_types = cast(dict[str, SaTypeFactory], _SA_TYPES)
    dialect = DialectTypes.SQLITE
    dialect_paramaters = frozenset(get_args(SqliteTypeParameters))

    @classmethod
    def reflected_type_facts(cls, sa_type: object) -> ReflectedTypeFacts:
        """SQLAlchemy spells multi-word type names with underscores in class
        names (``DOUBLE_PRECISION``), so they are normalized back to the SQL
        spelling (``double precision``) to match the dialect type names."""
        facts = super().reflected_type_facts(sa_type)
        return facts._replace(sql_type=facts.sql_type.replace("_", " "))

    @classmethod
    def render_type(cls, column: ColumnLike) -> str:
        t = column.type.lower()

        if t in cls._length_types_char:
            if column.max_length is None or column.max_length <= 0:
                return t
            return f"{t}({column.max_length})"

        if t in cls._numerical_parametise:
            if column.precision is None or column.precision == 0:
                return t
            if column.scale is None or column.scale == 0:
                return f"{t}({column.precision})"
            return f"{t}({column.precision}, {column.scale})"

        return t

    @classmethod
    def str_length(cls, column: ColumnLike) -> int | None:
        t = column.type.lower()

        if column.max_length is None or column.max_length <= 0:
            return None
        if t in cls._length_types_char:
            return column.max_length
        return None


# Pyright checks that every key we *write* is a valid SqliteType, but not that
# all members are present. This guard closes that gap at import time.
_missing = set(get_args(SqliteTypeParameters)) - SqliteMap.py_types.keys()
assert not _missing, f"SqliteMap.py_types is missing SQL types: {sorted(_missing)}"
_missing = set(get_args(SqliteTypeParameters)) - SqliteMap.sa_types.keys()
assert not _missing, f"SqliteMap.sa_types is missing SQL types: {sorted(_missing)}"
