from typing import TypeAlias, get_args
from enum import StrEnum

class SqlServerODBC(StrEnum):
    DRIVER_17 = "ODBC Driver 17 for SQL Server"
    DRIVER_11 = "ODBC Driver 11 for SQL Server"
    SQL_SERVER = "SQL Server"


class SqlServerNative(StrEnum):
    CLIENT_11 = "SQL Server Native Client 11.0"
    CLIENT_10 = "SQL Server Native Client 10.0"

SqlServerDrivers: TypeAlias = SqlServerODBC | SqlServerNative

_AUTH_MAP: dict[str, SqlServerDrivers] = {
    member.value: member
    for enum_type in get_args(SqlServerDrivers)
    for member in enum_type
}

def parse_sql_server_driver(value: str) -> SqlServerDrivers:
    if (auth := _AUTH_MAP.get(value)) is None:
        raise ValueError(f"Invalid sql server driver: {value!r}")
    return auth

