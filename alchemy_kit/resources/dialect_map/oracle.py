from typing import cast, get_args

from alchemy_kit.types.dialect_types import DialectTypes

from ._base import ColumnLike, DialectMap
from ...types.sql_type_parameters import OracleTypeParameters


class OracleMap(DialectMap[OracleTypeParameters]):

    _PY_TYPES: dict[OracleTypeParameters, str] = {
        # Numerics (Decimal is not imported by the template, so use float)
        "number": "float",
        "float": "float",
        "binary_float": "float",
        "binary_double": "float",
        "integer": "int",
        "int": "int",
        "smallint": "int",
        "dec": "float",
        "decimal": "float",
        "numeric": "float",
        # Character strings
        "char": "str",
        "nchar": "str",
        "varchar": "str",
        "varchar2": "str",
        "nvarchar2": "str",
        "long": "str",
        # Large objects (character)
        "clob": "str",
        "nclob": "str",
        # Date / time (Oracle DATE carries a time component)
        "date": "datetime",
        "timestamp": "datetime",
        "timestamp with time zone": "datetime",
        "timestamp with local time zone": "datetime",
        "interval year to month": "Any",
        "interval day to second": "Any",
        # Binary / large objects
        "raw": "Any",
        "long raw": "Any",
        "blob": "Any",
        "bfile": "Any",
        # Row identifiers
        "rowid": "str",
        "urowid": "str",
        # XML
        "xmltype": "str",
    }

    # SQL type name buckets (Oracle lengths reported in characters/bytes as-is)
    _length_types_char: set[OracleTypeParameters] = {
        "char", "nchar", "varchar", "varchar2", "nvarchar2",
    }
    _length_types_bin: set[OracleTypeParameters] = {"raw"}
    _numerical_parametise: set[OracleTypeParameters] = {
        "number", "dec", "decimal", "numeric",
    }
    _numerical_approximation: OracleTypeParameters = "float"
    _date_types: set[OracleTypeParameters] = {
        "timestamp", "timestamp with time zone", "timestamp with local time zone",
    }

    # Parent parameters
    py_types = cast(dict[str, str], _PY_TYPES)
    dialect = DialectTypes.ORACLE
    dialect_paramaters = frozenset(get_args(OracleTypeParameters))

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
                if " " in t:
                    head, tail = t.split(" ", 1)
                    return f"{head}({column.scale}) {tail}"
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


# Pyright checks that every key we *write* is a valid OracleType, but not that
# all members are present. This guard closes that gap at import time.
_missing = set(get_args(OracleTypeParameters)) - OracleMap.py_types.keys()
assert not _missing, f"OracleMap.py_types is missing SQL types: {sorted(_missing)}"
