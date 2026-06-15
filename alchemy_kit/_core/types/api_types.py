from typing import Literal, TypeAlias, Union


SqlServerApi: TypeAlias = Literal[
    "pyodbc",
    # "pymssql",
    # "aioodbc",
]

PostgreApi: TypeAlias = Literal[
    "psycopg",
    #"psycopg2",
    #"asyncpg",
    "pg8000",
    "psycopg2cffi",
]

MySqlApi: TypeAlias = Literal[
    "mysqldb",
    "pymysql",
    "mysqlconnector",
    # "asyncmy",
    # "aiomysql",
]

MariaDbApi: TypeAlias = Literal[
    "mariadbconnector",
    "pymysql",
    "mysqlconnector",
    # "asyncmy",
    # "aiomysql",
]

OracleApi: TypeAlias = Literal[
    "oracledb",
    "cx_oracle",
]

ApiTypes: TypeAlias = SqlServerApi # Union[SqlServerApi, PostgreApi, MySqlApi, MariaDbApi, OracleApi]
