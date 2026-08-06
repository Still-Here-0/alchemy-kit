from typing import cast, get_args


from sqlalchemy.dialects import postgresql as sa_pg
from sqlalchemy.types import NullType

from ._base import ColumnLike, DialectMap, ReflectedTypeFacts, SaTypeFactory
from ...types.py_type_parameters import PyTypeParameters
from ...types.sql_type_parameters import PostgresqlTypeParameters
from ...types.returning_support import ReturningSupport
from ...types.statement_limits import StatementLimits


class PostgresqlMap(DialectMap[PostgresqlTypeParameters]):

    _PY_TYPES: dict[PostgresqlTypeParameters, PyTypeParameters] = {
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
        # Reflection-emitted names
        "enum": "str",
        "array": "Any",
    }

    _SA_TYPES: dict[PostgresqlTypeParameters, SaTypeFactory] = {
        # Integers
        "smallint": sa_pg.SMALLINT,
        "integer": sa_pg.INTEGER,
        "int": sa_pg.INTEGER,
        "int2": sa_pg.SMALLINT,
        "int4": sa_pg.INTEGER,
        "bigint": sa_pg.BIGINT,
        "int8": sa_pg.BIGINT,
        # Auto-increment
        "smallserial": sa_pg.SMALLINT,
        "serial": sa_pg.INTEGER,
        "serial2": sa_pg.SMALLINT,
        "serial4": sa_pg.INTEGER,
        "bigserial": sa_pg.BIGINT,
        "serial8": sa_pg.BIGINT,
        # Boolean
        "boolean": sa_pg.BOOLEAN,
        "bool": sa_pg.BOOLEAN,
        # Exact numerics
        "decimal": sa_pg.NUMERIC,
        "numeric": sa_pg.NUMERIC,
        # Approximate numerics
        "real": sa_pg.REAL,
        "float4": sa_pg.REAL,
        "double precision": sa_pg.DOUBLE_PRECISION,
        "float8": sa_pg.DOUBLE_PRECISION,
        "money": sa_pg.MONEY,
        # Character strings
        "character": sa_pg.CHAR,
        "char": sa_pg.CHAR,
        "character varying": sa_pg.VARCHAR,
        "varchar": sa_pg.VARCHAR,
        "bpchar": sa_pg.CHAR,
        "text": sa_pg.TEXT,
        "name": sa_pg.TEXT,
        # Date / time
        "date": sa_pg.DATE,
        "timestamp": sa_pg.TIMESTAMP,
        "timestamp without time zone": sa_pg.TIMESTAMP,
        "timestamp with time zone": lambda: sa_pg.TIMESTAMP(timezone=True),
        "timestamptz": lambda: sa_pg.TIMESTAMP(timezone=True),
        "time": sa_pg.TIME,
        "time without time zone": sa_pg.TIME,
        "time with time zone": lambda: sa_pg.TIME(timezone=True),
        "timetz": lambda: sa_pg.TIME(timezone=True),
        "interval": sa_pg.INTERVAL,
        # Binary
        "bytea": sa_pg.BYTEA,
        # UUID
        "uuid": sa_pg.UUID,
        # JSON
        "json": sa_pg.JSON,
        "jsonb": sa_pg.JSONB,
        # Bit strings
        "bit": sa_pg.BIT,
        "bit varying": lambda: sa_pg.BIT(varying=True),
        "varbit": lambda: sa_pg.BIT(varying=True),
        # Network address
        "cidr": sa_pg.CIDR,
        "inet": sa_pg.INET,
        "macaddr": sa_pg.MACADDR,
        "macaddr8": sa_pg.MACADDR8,
        # Geometric
        "point": NullType,
        "line": NullType,
        "lseg": NullType,
        "box": NullType,
        "path": NullType,
        "polygon": NullType,
        "circle": NullType,
        # Range
        "int4range": sa_pg.INT4RANGE,
        "int8range": sa_pg.INT8RANGE,
        "numrange": sa_pg.NUMRANGE,
        "tsrange": sa_pg.TSRANGE,
        "tstzrange": sa_pg.TSTZRANGE,
        "daterange": sa_pg.DATERANGE,
        # Text search
        "tsvector": sa_pg.TSVECTOR,
        "tsquery": sa_pg.TSQUERY,
        # XML / other
        "xml": NullType,
        "oid": sa_pg.OID,
        # Reflection-emitted names
        "enum": NullType,
        "array": NullType,
    }

    # Reflected class name -> dialect type name (catalog types '"char"' and
    # 'name' reflect as the generic sqltypes.String; FLOAT is stored as
    # double precision)
    _REFLECTED_SYNONYMS: dict[str, PostgresqlTypeParameters] = {
        "string": "text",
        "float": "double precision",
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
    py_types = cast(dict[str, PyTypeParameters], _PY_TYPES)
    sa_types = cast(dict[str, SaTypeFactory], _SA_TYPES)
    _reflected_synonyms = cast(dict[str, str], _REFLECTED_SYNONYMS)
    name = "postgresql"
    _sa_dialect_factory = sa_pg.dialect
    dialect_paramaters = frozenset(get_args(PostgresqlTypeParameters))
    limits = StatementLimits(max_params=65535)
    returning = ReturningSupport(insert=True, update=True, delete=True)

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
_missing = set(get_args(PostgresqlTypeParameters)) - PostgresqlMap.sa_types.keys()
assert not _missing, f"PostgresqlMap.sa_types is missing SQL types: {sorted(_missing)}"
