from typing import TypeAlias, Literal


MssqlTypeParameters: TypeAlias = Literal[
    # Integers
    "bigint", "int", "smallint", "tinyint",
    # Boolean
    "bit",
    # Exact / approximate numerics
    "decimal", "numeric", "money", "smallmoney", "float", "real",
    # Date / time
    "date", "datetime", "datetime2", "smalldatetime", "datetimeoffset", "time",
    # Character strings
    "char", "varchar", "nchar", "nvarchar", "text", "ntext",
    "xml", "sysname", "uniqueidentifier",
    # Binary / other
    "binary", "varbinary", "image", "timestamp", "rowversion", "sql_variant",
]


MysqlTypeParameters: TypeAlias = Literal[
    # Integers
    "tinyint", "smallint", "mediumint", "int", "integer", "bigint",
    # Boolean (synonyms for tinyint(1))
    "bool", "boolean",
    # Bit-field
    "bit",
    # Exact / approximate numerics
    "decimal", "dec", "numeric", "fixed",
    "float", "double", "double precision", "real",
    # Date / time
    "date", "datetime", "timestamp", "time", "year",
    # Character strings
    "char", "varchar",
    "tinytext", "text", "mediumtext", "longtext",
    # Enumerated / set
    "enum", "set",
    # Binary strings
    "binary", "varbinary",
    "tinyblob", "blob", "mediumblob", "longblob",
    # JSON
    "json",
    # Spatial
    "geometry", "point", "linestring", "polygon",
    "multipoint", "multilinestring", "multipolygon", "geometrycollection",
]


# MariaDB is a MySQL fork: it shares MySQL's type surface and adds a few of its
# own (native uuid, dedicated inet4/inet6, row types).
MariadbTypeParameters: TypeAlias = Literal[
    # Integers
    "tinyint", "smallint", "mediumint", "int", "integer", "bigint",
    # Boolean (synonyms for tinyint(1))
    "bool", "boolean",
    # Bit-field
    "bit",
    # Exact / approximate numerics
    "decimal", "dec", "numeric", "fixed",
    "float", "double", "double precision", "real",
    # Date / time
    "date", "datetime", "timestamp", "time", "year",
    # Character strings
    "char", "varchar",
    "tinytext", "text", "mediumtext", "longtext",
    # Enumerated / set
    "enum", "set",
    # Binary strings
    "binary", "varbinary",
    "tinyblob", "blob", "mediumblob", "longblob",
    # JSON (alias of longtext in MariaDB)
    "json",
    # MariaDB-specific
    "uuid", "inet4", "inet6",
    # Spatial
    "geometry", "point", "linestring", "polygon",
    "multipoint", "multilinestring", "multipolygon", "geometrycollection",
]


PostgresqlTypeParameters: TypeAlias = Literal[
    # Integers
    "smallint", "integer", "int", "int2", "int4", "bigint", "int8",
    # Auto-increment
    "smallserial", "serial", "serial2", "serial4", "bigserial", "serial8",
    # Boolean
    "boolean", "bool",
    # Exact / approximate numerics
    "decimal", "numeric",
    "real", "float4", "double precision", "float8", "money",
    # Character strings
    "character", "char", "character varying", "varchar", "bpchar", "text", "name",
    # Date / time
    "date",
    "timestamp", "timestamp without time zone", "timestamp with time zone", "timestamptz",
    "time", "time without time zone", "time with time zone", "timetz",
    "interval",
    # Binary
    "bytea",
    # UUID
    "uuid",
    # JSON
    "json", "jsonb",
    # Bit strings
    "bit", "bit varying", "varbit",
    # Network address
    "cidr", "inet", "macaddr", "macaddr8",
    # Geometric
    "point", "line", "lseg", "box", "path", "polygon", "circle",
    # Range
    "int4range", "int8range", "numrange", "tsrange", "tstzrange", "daterange",
    # Text search
    "tsvector", "tsquery",
    # XML / other
    "xml", "oid",
]


OracleTypeParameters: TypeAlias = Literal[
    # Numerics
    "number", "float", "binary_float", "binary_double",
    "integer", "int", "smallint", "dec", "decimal", "numeric",
    # Character strings
    "char", "nchar", "varchar", "varchar2", "nvarchar2", "long",
    # Large objects (character)
    "clob", "nclob",
    # Date / time
    "date",
    "timestamp",
    "timestamp with time zone",
    "timestamp with local time zone",
    "interval year to month",
    "interval day to second",
    # Binary / large objects
    "raw", "long raw", "blob", "bfile",
    # Row identifiers
    "rowid", "urowid",
    # XML
    "xmltype",
]


# SQLite uses dynamic type affinity: any declared type name is accepted and
# mapped to one of five affinities. These are the type names commonly emitted
# by other engines / ORMs that SQLite recognises for affinity resolution.
SqliteTypeParameters: TypeAlias = Literal[
    # INTEGER affinity
    "int", "integer", "tinyint", "smallint", "mediumint", "bigint",
    "unsigned big int", "int2", "int8",
    # REAL affinity
    "real", "double", "double precision", "float",
    # NUMERIC affinity
    "numeric", "decimal", "boolean", "date", "datetime",
    # TEXT affinity
    "character", "varchar", "varying character", "nchar",
    "native character", "nvarchar", "text", "clob",
    # BLOB affinity (no datatype specified)
    "blob",
]

