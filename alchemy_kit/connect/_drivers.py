from importlib.util import find_spec
from typing import NamedTuple


class _DriverSpec(NamedTuple):
    module: str
    pip_package: str


# Keyed by the DBAPI name used in the SQLAlchemy URL (the api_types enum
# values). The import module and pip package differ for several drivers.
_DRIVER_SPECS: dict[str, _DriverSpec] = {
    # SQL Server
    "pyodbc": _DriverSpec("pyodbc", "pyodbc"),
    "pymssql": _DriverSpec("pymssql", "pymssql"),
    "aioodbc": _DriverSpec("aioodbc", "aioodbc"),
    # PostgreSQL
    "psycopg": _DriverSpec("psycopg", "psycopg[binary]"),
    "pg8000": _DriverSpec("pg8000", "pg8000"),
    "psycopg2cffi": _DriverSpec("psycopg2cffi", "psycopg2cffi"),
    # MySQL / MariaDB
    "mysqldb": _DriverSpec("MySQLdb", "mysqlclient"),
    "pymysql": _DriverSpec("pymysql", "pymysql"),
    "mysqlconnector": _DriverSpec("mysql.connector", "mysql-connector-python"),
    "mariadbconnector": _DriverSpec("mariadb", "mariadb"),
    # Oracle
    "oracledb": _DriverSpec("oracledb", "oracledb"),
    "cx_oracle": _DriverSpec("cx_Oracle", "cx_Oracle"),
}


def require_driver(api: str, extra: str) -> None:
    """Fail fast when the DBAPI driver behind ``api`` is not installed.

    Raises ``ImportError`` with the install command naming the project extra
    for ``extra`` (and the exact pip package), instead of letting SQLAlchemy
    fail with a bare ``ModuleNotFoundError`` at engine-creation time.
    """
    spec = _DRIVER_SPECS.get(str(api))
    if spec is None:
        return

    if not _module_available(spec.module):
        raise ImportError(
            f"The '{api}' DBAPI driver is not installed. Install it with:\n"
            f"    pip install alchemy-kit[{extra}]\n"
            f"or install the driver directly:\n"
            f"    pip install {spec.pip_package}"
        )


def _module_available(module: str) -> bool:
    try:
        return find_spec(module) is not None
    except ModuleNotFoundError:
        return False
