from typing import cast, get_args

from alchemy_kit.types.dialect_types import DialectTypes

from ._base import ColumnLike, DialectMap, ReflectedTypeFacts
from ...types.sql_type_parameters import PostgresqlTypeParameters


class PostgresqlMap(DialectMap[PostgresqlTypeParameters]):

    _PY_TYPES: dict[PostgresqlTypeParameters, str] = {
        # Integers
        "smallint": "int",
        "integer": "int",
        "int": "int",
        "int2": "int",
        "int4": "int",
        "bigint": "int",
        "int8": "int",
        # Auto-increment
        "smallserial": "int",
        "serial": "int",
        "serial2": "int",
        "serial4": "int",
        "bigserial": "int",
        "serial8": "int",
        # Boolean
        "boolean": "bool",
        "bool": "bool",
        # Exact numerics (Decimal is not imported by the template, so use float)
        "decimal": "float",
        "numeric": "float",
        # Approximate numerics
        "real": "float",
        "float4": "float",
        "double precision": "float",
        "float8": "float",
        "money": "float",
        # Character strings
        "character": "str",
        "char": "str",
        "character varying": "str",
        "varchar": "str",
        "bpchar": "str",
        "text": "str",
        "name": "str",
        # Date / time
        "date": "date",
        "timestamp": "datetime",
        "timestamp without time zone": "datetime",
        "timestamp with time zone": "datetime",
        "timestamptz": "datetime",
        "time": "Any",
        "time without time zone": "Any",
        "time with time zone": "Any",
        "timetz": "Any",
        "interval": "Any",
        # Binary
        "bytea": "Any",
        # UUID
        "uuid": "str",
        # JSON
        "json": "Any",
        "jsonb": "Any",
        # Bit strings
        "bit": "Any",
        "bit varying": "Any",
        "varbit": "Any",
        # Network address
        "cidr": "str",
        "inet": "str",
        "macaddr": "str",
        "macaddr8": "str",
        # Geometric
        "point": "Any",
        "line": "Any",
        "lseg": "Any",
        "box": "Any",
        "path": "Any",
        "polygon": "Any",
        "circle": "Any",
        # Range
        "int4range": "Any",
        "int8range": "Any",
        "numrange": "Any",
        "tsrange": "Any",
        "tstzrange": "Any",
        "daterange": "Any",
        # Text search
        "tsvector": "str",
        "tsquery": "str",
        # XML / other
        "xml": "str",
        "oid": "int",
    }

    # SQL type name buckets (PostgreSQL lengths are in characters)
    _length_types_char: set[PostgresqlTypeParameters] = {
        "character", "char", "character varying", "varchar", "bpchar",
    }
    _length_types_bit: set[PostgresqlTypeParameters] = {"bit", "bit varying", "varbit"}
    _numerical_parametise: set[PostgresqlTypeParameters] = {"decimal", "numeric"}
    _date_types: set[PostgresqlTypeParameters] = {
        "time", "time without time zone", "time with time zone", "timetz",
        "timestamp", "timestamp without time zone", "timestamp with time zone", "timestamptz",
    }

    # Parent parameters
    py_types = cast(dict[str, str], _PY_TYPES)
    dialect = DialectTypes.POSTGRESQL
    dialect_paramaters = frozenset(get_args(PostgresqlTypeParameters))

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

        if t in cls._length_types_char or t in cls._length_types_bit:
            if column.max_length is None or column.max_length <= 0:
                return t
            return f"{t}({column.max_length})"

        if t in cls._numerical_parametise:
            if column.precision is None or column.precision == 0:
                return t
            if column.scale is None or column.scale == 0:
                return f"{t}({column.precision})"
            return f"{t}({column.precision}, {column.scale})"

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


# Pyright checks that every key we *write* is a valid PostgresqlType, but not
# that all members are present. This guard closes that gap at import time.
_missing = set(get_args(PostgresqlTypeParameters)) - PostgresqlMap.py_types.keys()
assert not _missing, f"PostgresqlMap.py_types is missing SQL types: {sorted(_missing)}"
