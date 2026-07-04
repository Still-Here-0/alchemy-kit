
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

