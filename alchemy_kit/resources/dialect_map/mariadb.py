from typing import cast, get_args

from alchemy_kit.types.dialect_types import DialectTypes

from ._base import ColumnLike, DialectMap
from ...types.sql_type_parameters import MariadbTypeParameters


class MariadbMap(DialectMap[MariadbTypeParameters]):

    _PY_TYPES: dict[MariadbTypeParameters, str] = {
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
        # MariaDB-specific
        "uuid": "str",
        "inet4": "str",
        "inet6": "str",
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

    # SQL type name buckets (MariaDB lengths are in characters)
    _length_types_char: set[MariadbTypeParameters] = {"char", "varchar"}
    _length_types_bin: set[MariadbTypeParameters] = {"binary", "varbinary"}
    _numerical_parametise: set[MariadbTypeParameters] = {"decimal", "dec", "numeric", "fixed"}
    _numerical_approximation: MariadbTypeParameters = "float"
    _date_types: set[MariadbTypeParameters] = {"datetime", "timestamp", "time"}

    # Parent parameters
    py_types = cast(dict[str, str], _PY_TYPES)
    dialect = DialectTypes.MARIADB
    dialect_paramaters = frozenset(get_args(MariadbTypeParameters))

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


# Pyright checks that every key we *write* is a valid MariadbType, but not that
# all members are present. This guard closes that gap at import time.
_missing = set(get_args(MariadbTypeParameters)) - MariadbMap.py_types.keys()
assert not _missing, f"MariadbMap.py_types is missing SQL types: {sorted(_missing)}"
