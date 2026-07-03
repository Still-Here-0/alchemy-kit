from ..types.dialect_types import DialectTypes

_mssql_map: dict[str, str] = {
    # Integers
    "bigint": "int",
    "int": "int",
    "smallint": "int",
    "tinyint": "int",
    # Boolean
    "bit": "bool",
    # Exact numerics (Decimal is not imported by the template, so use float)
    "decimal": "float", # TODO: This should be a decimal too, but got some inconsistencies
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

def get_type(dialect: DialectTypes, slq_type: str) -> str:
    match dialect:
        case DialectTypes.MSSQL:
            return _mssql_map[slq_type]
    
    raise ValueError(f"Dialect not mapped on dialect_map: {dialect}")

