from typing import cast, get_args

from ._base import ColumnLike, DialectParameterMap
from ...types._sql_type_parameters import MssqlTypeParameters


class MssqlParameterMap(DialectParameterMap):

    _PY_TYPES: dict[MssqlTypeParameters, str] = {
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
    py_types = cast(dict[str, str], _PY_TYPES)

    # SQL type name buckets
    _length_types_char: set[MssqlTypeParameters] = {"char", "varchar"}        # 1 byte/char
    _length_types_nchar: set[MssqlTypeParameters] = {"nchar", "nvarchar"}     # 2 bytes/char (Unicode)
    _length_types_bin: set[MssqlTypeParameters] = {"binary", "varbinary"}
    _numerical_parametise: set[MssqlTypeParameters] = {"decimal", "numeric"}
    _numerical_approximation: MssqlTypeParameters = "float"
    _date_types: set[MssqlTypeParameters] = {"time", "datetime2", "datetimeoffset"}

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


# Pyright checks that every key we *write* is a valid MssqlType, but not that
# all members are present. This guard closes that gap at import time.
_missing = set(get_args(MssqlTypeParameters)) - MssqlParameterMap.py_types.keys()
assert not _missing, f"MssqlMap.py_types is missing SQL types: {sorted(_missing)}"
