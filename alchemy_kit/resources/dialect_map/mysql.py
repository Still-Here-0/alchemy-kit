from typing import cast, get_args


from sqlalchemy.dialects import mysql as sa_mysql
from sqlalchemy.types import NullType

from ._base import ColumnLike, DialectMap, SaTypeFactory
from ...types.py_type_parameters import PyTypeParameters
from ...types.sql_type_parameters import MysqlTypeParameters
from ...types.returning_support import ReturningSupport
from ...types.statement_limits import StatementLimits


class MysqlMap(DialectMap[MysqlTypeParameters]):

    _PY_TYPES: dict[MysqlTypeParameters, PyTypeParameters] = {
        # Integers
        "tinyint": "int",
        "smallint": "int",
        "mediumint": "int",
        "int": "int",
        "integer": "int",
        "bigint": "int",
        # Boolean
        "bool": "bool",
        "boolean": "bool",
        # Bit-field
        "bit": "Any",
        # Exact numerics (Decimal is not imported by the template, so use float)
        "decimal": "float",
        "dec": "float",
        "numeric": "float",
        "fixed": "float",
        # Approximate numerics
        "float": "float",
        "double": "float",
        "double precision": "float",
        "real": "float",
        # Date / time
        "date": "date",
        "datetime": "datetime",
        "timestamp": "datetime",
        "time": "Any",
        "year": "int",
        # Character strings
        "char": "str",
        "varchar": "str",
        "tinytext": "str",
        "text": "str",
        "mediumtext": "str",
        "longtext": "str",
        # Enumerated / set
        "enum": "str",
        "set": "str",
        # Binary strings
        "binary": "Any",
        "varbinary": "Any",
        "tinyblob": "Any",
        "blob": "Any",
        "mediumblob": "Any",
        "longblob": "Any",
        # JSON
        "json": "Any",
        # Spatial
        "geometry": "Any",
        "point": "Any",
        "linestring": "Any",
        "polygon": "Any",
        "multipoint": "Any",
        "multilinestring": "Any",
        "multipolygon": "Any",
        "geometrycollection": "Any",
    }

    _SA_TYPES: dict[MysqlTypeParameters, SaTypeFactory] = {
        # Integers
        "tinyint": sa_mysql.TINYINT,
        "smallint": sa_mysql.SMALLINT,
        "mediumint": sa_mysql.MEDIUMINT,
        "int": sa_mysql.INTEGER,
        "integer": sa_mysql.INTEGER,
        "bigint": sa_mysql.BIGINT,
        # Boolean
        "bool": sa_mysql.BOOLEAN,
        "boolean": sa_mysql.BOOLEAN,
        # Bit-field
        "bit": sa_mysql.BIT,
        # Exact numerics
        "decimal": sa_mysql.DECIMAL,
        "dec": sa_mysql.DECIMAL,
        "numeric": sa_mysql.NUMERIC,
        "fixed": sa_mysql.DECIMAL,
        # Approximate numerics
        "float": sa_mysql.FLOAT,
        "double": sa_mysql.DOUBLE,
        "double precision": sa_mysql.DOUBLE,
        "real": sa_mysql.REAL,
        # Date / time
        "date": sa_mysql.DATE,
        "datetime": sa_mysql.DATETIME,
        "timestamp": sa_mysql.TIMESTAMP,
        "time": sa_mysql.TIME,
        "year": sa_mysql.YEAR,
        # Character strings
        "char": sa_mysql.CHAR,
        "varchar": sa_mysql.VARCHAR,
        "tinytext": sa_mysql.TINYTEXT,
        "text": sa_mysql.TEXT,
        "mediumtext": sa_mysql.MEDIUMTEXT,
        "longtext": sa_mysql.LONGTEXT,
        # Enumerated / set
        "enum": sa_mysql.ENUM,
        "set": sa_mysql.SET,
        # Binary strings
        "binary": sa_mysql.BINARY,
        "varbinary": sa_mysql.VARBINARY,
        "tinyblob": sa_mysql.TINYBLOB,
        "blob": sa_mysql.BLOB,
        "mediumblob": sa_mysql.MEDIUMBLOB,
        "longblob": sa_mysql.LONGBLOB,
        # JSON
        "json": sa_mysql.JSON,
        # Spatial
        "geometry": NullType,
        "point": NullType,
        "linestring": NullType,
        "polygon": NullType,
        "multipoint": NullType,
        "multilinestring": NullType,
        "multipolygon": NullType,
        "geometrycollection": NullType,
    }

    # Reflected class name -> dialect type name (NCHAR/NVARCHAR are national
    # charset variants MySQL stores as char/varchar)
    _REFLECTED_SYNONYMS: dict[str, MysqlTypeParameters] = {
        "nchar": "char",
        "nvarchar": "varchar",
    }

    # SQL type name buckets (MySQL lengths are in characters)
    _length_types_char: set[MysqlTypeParameters] = {"char", "varchar"}
    _length_types_bin: set[MysqlTypeParameters] = {"binary", "varbinary"}
    _numerical_parametise: set[MysqlTypeParameters] = {"decimal", "dec", "numeric", "fixed"}
    _numerical_approximation: MysqlTypeParameters = "float"
    _date_types: set[MysqlTypeParameters] = {"datetime", "timestamp", "time"}

    # Parent parameters
    py_types = cast(dict[str, PyTypeParameters], _PY_TYPES)
    sa_types = cast(dict[str, SaTypeFactory], _SA_TYPES)
    _reflected_synonyms = cast(dict[str, str], _REFLECTED_SYNONYMS)
    name = "mysql"
    _sa_dialect_factory = sa_mysql.dialect
    dialect_paramaters = frozenset(get_args(MysqlTypeParameters))
    _quote_open = "`"
    _quote_close = "`"
    limits = StatementLimits(max_params=65535)
    returning = ReturningSupport()

    @classmethod
    def render_type(cls, column: ColumnLike) -> str:
        t = column.type.lower()

        if t in cls._length_types_char or t in cls._length_types_bin:
            if column.max_length is None or column.max_length <= 0:
                return t
            return f"{t}({column.max_length})"

        if t in cls._numerical_parametise:
            if column.precision is None or column.precision == 0:
                return t
            if column.scale is None or column.scale == 0:
                return f"{t}({column.precision})"
            return f"{t}({column.precision}, {column.scale})"

        if t == cls._numerical_approximation:
            if column.precision is not None and column.precision > 0:
                return f"float({column.precision})"
            return cls._numerical_approximation

        if t in cls._date_types:
            if column.scale is not None and column.scale > 0:
                return f"{t}({column.scale})"
            return t

        return t

    @classmethod
    def str_length(cls, column: ColumnLike) -> int | None:
        t = column.type.lower()

        if column.max_length is None or column.max_length <= 0:
            return None
        if t in cls._length_types_char:
            return column.max_length
        return None


# Pyright checks that every key we *write* is a valid MysqlType, but not that
# all members are present. This guard closes that gap at import time.
_missing = set(get_args(MysqlTypeParameters)) - MysqlMap.py_types.keys()
assert not _missing, f"MysqlMap.py_types is missing SQL types: {sorted(_missing)}"
_missing = set(get_args(MysqlTypeParameters)) - MysqlMap.sa_types.keys()
assert not _missing, f"MysqlMap.sa_types is missing SQL types: {sorted(_missing)}"
