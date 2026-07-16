from typing import cast, get_args

from alchemy_kit.types.dialect_types import DialectTypes

from sqlalchemy.dialects import mssql as sa_mssql

from ._base import ColumnLike, DialectMap, ReflectedTypeFacts, SaTypeFactory
from ...types.py_type_parameters import PyTypeParameters
from ...types.sql_type_parameters import MssqlTypeParameters


class MssqlMap(DialectMap[MssqlTypeParameters]):

    _PY_TYPES: dict[MssqlTypeParameters, PyTypeParameters] = {
        # Integers
        "bigint": "int",
        "int": "int",
        "smallint": "int",
        "tinyint": "int",
        # Boolean
        "bit": "bool",
        # Exact numerics (Decimal is not imported by the template, so use float)
        "decimal": "float",  # TODO: This should be a decimal too, but got some inconsistencies
        "numeric": "float",
        "money": "float",
        "smallmoney": "float",
        # Approximate numerics
        "float": "float",
        "real": "float",
        # Date / time
        "date": "date",
        "datetime": "datetime",
        "datetime2": "datetime",
        "smalldatetime": "datetime",
        "datetimeoffset": "datetime",
        "time": "Any",
        # Character strings
        "char": "str",
        "varchar": "str",
        "nchar": "str",
        "nvarchar": "str",
        "text": "str",
        "ntext": "str",
        "xml": "str",
        "sysname": "str",
        "uniqueidentifier": "str",
        # Binary / other
        "binary": "Any",
        "varbinary": "Any",
        "image": "Any",
        "timestamp": "Any",
        "rowversion": "Any",
        "sql_variant": "Any",
    }

    _SA_TYPES: dict[MssqlTypeParameters, SaTypeFactory] = {
        # Integers
        "bigint": sa_mssql.BIGINT,
        "int": sa_mssql.INTEGER,
        "smallint": sa_mssql.SMALLINT,
        "tinyint": sa_mssql.TINYINT,
        # Boolean
        "bit": sa_mssql.BIT,
        # Exact numerics
        "decimal": sa_mssql.DECIMAL,
        "numeric": sa_mssql.NUMERIC,
        "money": sa_mssql.MONEY,
        "smallmoney": sa_mssql.SMALLMONEY,
        # Approximate numerics
        "float": sa_mssql.FLOAT,
        "real": sa_mssql.REAL,
        # Date / time
        "date": sa_mssql.DATE,
        "datetime": sa_mssql.DATETIME,
        "datetime2": sa_mssql.DATETIME2,
        "smalldatetime": sa_mssql.SMALLDATETIME,
        "datetimeoffset": sa_mssql.DATETIMEOFFSET,
        "time": sa_mssql.TIME,
        # Character strings
        "char": sa_mssql.CHAR,
        "varchar": sa_mssql.VARCHAR,
        "nchar": sa_mssql.NCHAR,
        "nvarchar": sa_mssql.NVARCHAR,
        "text": sa_mssql.TEXT,
        "ntext": sa_mssql.NTEXT,
        "xml": sa_mssql.XML,
        "sysname": sa_mssql.NVARCHAR,
        "uniqueidentifier": sa_mssql.UNIQUEIDENTIFIER,
        # Binary / other
        "binary": sa_mssql.BINARY,
        "varbinary": sa_mssql.VARBINARY,
        "image": sa_mssql.IMAGE,
        "timestamp": sa_mssql.TIMESTAMP,
        "rowversion": sa_mssql.ROWVERSION,
        "sql_variant": sa_mssql.SQL_VARIANT,
    }

    # Reflected class name -> dialect type name ("int" reflects as
    # sqltypes.INTEGER; "double precision" is an alias of float(53))
    _REFLECTED_SYNONYMS: dict[str, MssqlTypeParameters] = {
        "integer": "int",
        "double_precision": "float",
    }

    # SQL type name buckets
    _length_types_char: set[MssqlTypeParameters] = {"char", "varchar"}        # 1 byte/char
    _length_types_nchar: set[MssqlTypeParameters] = {"nchar", "nvarchar"}     # 2 bytes/char (Unicode)
    _length_types_bin: set[MssqlTypeParameters] = {"binary", "varbinary"}
    _numerical_parametise: set[MssqlTypeParameters] = {"decimal", "numeric"}
    _numerical_approximation: MssqlTypeParameters = "float"
    _date_types: set[MssqlTypeParameters] = {"time", "datetime2", "datetimeoffset"}

    # Parent parameters
    py_types = cast(dict[str, PyTypeParameters], _PY_TYPES)
    sa_types = cast(dict[str, SaTypeFactory], _SA_TYPES)
    _reflected_synonyms = cast(dict[str, str], _REFLECTED_SYNONYMS)
    dialect = DialectTypes.MSSQL
    dialect_paramaters = frozenset(get_args(MssqlTypeParameters))
    _quote_open = "["
    _quote_close = "]"
    max_insert_rows = 1000
    max_statement_params = 2100

    @classmethod
    def reflected_type_facts(cls, sa_type: object) -> ReflectedTypeFacts:
        """SQL Server convention: ``sys.columns.max_length`` is in *bytes*, so
        Unicode string lengths reported in characters by reflection are doubled
        to keep both extraction paths on the byte convention ``str_length``
        expects."""
        facts = super().reflected_type_facts(sa_type)

        if facts.sql_type in cls._length_types_nchar and facts.max_length > 0:
            facts = facts._replace(max_length=facts.max_length * 2)

        return facts

    @classmethod
    def render_type(cls, column: ColumnLike) -> str:
        t = column.type.lower()

        if t in cls._length_types_char or t in cls._length_types_nchar or t in cls._length_types_bin:
            if column.max_length is None or column.max_length == -1:
                return f"{t}(max)"
            if t in cls._length_types_nchar:
                return f"{t}({column.max_length // 2})"
            return f"{t}({column.max_length})"

        if t in cls._numerical_parametise:
            if column.precision is None:
                return t
            if column.scale is None or column.scale == 0:
                return f"{t}({column.precision})"
            return f"{t}({column.precision}, {column.scale})"

        if t == cls._numerical_approximation:
            if column.precision is not None and column.precision > 0:
                return f"float({column.precision})"
            return cls._numerical_approximation

        if t in cls._date_types:
            if column.scale is not None:
                return f"{t}({column.scale})"
            return t

        return t

    @classmethod
    def str_length(cls, column: ColumnLike) -> int | None:
        t = column.type.lower()

        if column.max_length is None or column.max_length == -1:
            return None
        if t in cls._length_types_nchar:
            return column.max_length // 2
        if t in cls._length_types_char:
            return column.max_length
        return None


# Pyright checks that every key we *write* is a valid MssqlType, but not that
# all members are present. This guard closes that gap at import time.
_missing = set(get_args(MssqlTypeParameters)) - MssqlMap.py_types.keys()
assert not _missing, f"MssqlMap.py_types is missing SQL types: {sorted(_missing)}"
_missing = set(get_args(MssqlTypeParameters)) - MssqlMap.sa_types.keys()
assert not _missing, f"MssqlMap.sa_types is missing SQL types: {sorted(_missing)}"
