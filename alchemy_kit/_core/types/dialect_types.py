from enum import StrEnum
from typing import TypeAlias, Literal


class DialectTypes(StrEnum):
    MSSQL = "mssql"
    MYSQL = "mysql"
    POSTGESQL = "postgesql"
    MARIADB = "mariadb"
    SQLITE = "sqlite"
    ORACLE = "oracle"

DialectTypesInput: TypeAlias = Literal["mssql", "mysql", "postgesql", "mariadb", "sqlite", "oracle"]
