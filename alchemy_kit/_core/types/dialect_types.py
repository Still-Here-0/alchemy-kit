from enum import StrEnum
from typing import TypeAlias, Literal


class DialectTypes(StrEnum):
    MSSQL = "mssql"
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    MARIADB = "mariadb"
    SQLITE = "sqlite"
    ORACLE = "oracle"

DialectTypesInput: TypeAlias = Literal["mssql", "mysql", "postgresql", "mariadb", "sqlite", "oracle"]
