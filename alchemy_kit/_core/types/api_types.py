from enum import StrEnum


class SqlServerApi(StrEnum):
    PYODBC = "pyodbc"
    PYMSSQL = "pymssql"
    AIOODBC = "aioodbc"


class PostgreApi(StrEnum):
    PSYCOPG = "psycopg"
    # PSYCOPG2 = "psycopg2"
    # ASYNCPG = "asyncpg"
    PG8000 = "pg8000"
    PSYCOPG2CFFI = "psycopg2cffi"


class MySqlApi(StrEnum):
    MYSQLDB = "mysqldb"
    PYMYSQL = "pymysql"
    MYSQLCONNECTOR = "mysqlconnector"
    # ASYNCMY = "asyncmy"
    # AIOMYSQL = "aiomysql"


class MariaDbApi(StrEnum):
    MARIADBCONNECTOR = "mariadbconnector"
    PYMYSQL = "pymysql"
    MYSQLCONNECTOR = "mysqlconnector"
    # ASYNCMY = "asyncmy"
    # AIOMYSQL = "aiomysql"


class OracleApi(StrEnum):
    ORACLEDB = "oracledb"
    CX_ORACLE = "cx_oracle"


