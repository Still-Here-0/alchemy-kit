import json
from pathlib import Path
from typing import Literal, Optional, cast, overload

import sqlalchemy
from dotenv import dotenv_values
from pydantic import SecretStr

from ..resources._settings import Settings
from ..types import _driver_types
from ..types.api_types import SqlServerApi
from ..types.auth_types import AuthType
from ..types.dialect_types import DialectTypes
from ..types.generic_path import GenericPath
from ._conn_builders import mssql
from ._drivers import require_driver
from ._info import ConnectionInfo

__all__ = [
    "from_json",
    "from_env",
    "from_values_mssql",
    "from_values_mysql",
    "from_values_postgresql",
    "from_values_mariadb",
    "from_values_sqlite",
    "from_values_oracle",
]

def from_json(json_path: GenericPath) -> dict[str, ConnectionInfo]:
    """Build the connections described by a JSON file.

    The JSON is a mapping of ``unique_id`` -> connection definition, where each
    definition holds the keys named in ``Settings.FileExtraction`` (dialect,
    auth, driver, server, ...). Each entry is dispatched by dialect and turned
    into a ``ConnectionInfo``.

    Args:
        json_path: Path to the JSON file describing the connections.

    Returns:
        One ``ConnectionInfo`` per entry, keyed by its ``unique_id``.

    Raises:
        ValueError: If ``json_path`` does not point to an existing file.
    """
    json_path = Path(json_path).resolve()
    if not json_path.is_file():
        raise ValueError(f"JSON file not found: '{json_path}'")

    connections = {}
    
    with json_path.open('r', encoding="UTF-8") as file:
        data: dict[str, dict[str, str]] = json.load(file)

        for unique_id, conn_data in data.items():
            dialect = DialectTypes(conn_data[Settings.FileExtraction.dialect_marker])
            connections[unique_id] = _match_dialect(dialect, unique_id, conn_data)
            
    return connections

def from_env(env_path: GenericPath) -> ConnectionInfo:
    """Build a single connection from a ``.env`` file.

    The file is read as a flat set of key/value pairs using the keys named in
    ``Settings.FileExtraction`` (dialect, auth, driver, server, ...) and
    dispatched by dialect into a ``ConnectionInfo``.

    Args:
        env_path: Path to the ``.env`` file describing the connection.

    Returns:
        The ``ConnectionInfo`` for the connection described in the file.

    Raises:
        ValueError: If ``env_path`` does not point to an existing file.
    """
    env_path = Path(env_path).resolve()
    if not env_path.is_file():
        raise ValueError(f".env file not found: '{env_path}'")

    env_data = cast(dict[str, str], dotenv_values(env_path))
    dialect = DialectTypes(env_data[Settings.FileExtraction.dialect_marker])

    return _match_dialect(dialect, env_data.get(Settings.FileExtraction.unique_id_marker), env_data)

_TRUE_VALUES = {"yes", "true", "1", "on"}
_FALSE_VALUES = {"no", "false", "0", "off"}

def _parse_optional_bool(value: Optional[str]) -> Optional[bool]:
    """Parse a connection-file flag into a tri-state bool (``None`` when unset)."""
    if value is None or value == "":
        return None
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError(f"Expected a boolean-like value, got {value!r}")

def _match_dialect(dialect: DialectTypes, unique_id: Optional[str], conn_data: dict[str, str]) -> ConnectionInfo: # CONTINUE
    """Dispatch a parsed connection definition to the right dialect builder.

    Reads the auth method (and, per dialect, the remaining keys named in
    ``Settings.FileExtraction``) from ``conn_data`` and delegates to the
    matching ``from_values_*`` builder.

    Args:
        dialect: The dialect of the connection to build.
        unique_id: Optional identifier for the connection; a random one is
            generated downstream when ``None``.
        conn_data: The raw key/value definition for a single connection.

    Returns:
        The ``ConnectionInfo`` produced by the dialect-specific builder.

    Raises:
        ValueError: If the auth method is unsupported for the dialect.
    """
    auth = AuthType(conn_data[Settings.FileExtraction.auth_marker])
    
    match dialect:
        case DialectTypes.MSSQL:
            driver = _driver_types.parse_sql_server_driver(conn_data[Settings.FileExtraction.driver_marker])
            api = SqlServerApi(conn_data.get(Settings.FileExtraction.api_marker, SqlServerApi.PYODBC))
            encrypt = _parse_optional_bool(conn_data.get(Settings.FileExtraction.encrypt_marker))
            trust_server_certificate = _parse_optional_bool(
                conn_data.get(Settings.FileExtraction.trust_server_certificate_marker)
            )

            if auth == AuthType.SQL_AUTH:
                return from_values_mssql(
                    auth,
                    driver,
                    conn_data[Settings.FileExtraction.server_marker],
                    conn_data[Settings.FileExtraction.database_marker],
                    user_name=conn_data[Settings.FileExtraction.user_name_marker],
                    user_pwd=SecretStr(conn_data[Settings.FileExtraction.user_pwd_marker]),
                    unique_id=unique_id,
                    api=cast(SqlServerApi, api),
                    encrypt=encrypt,
                    trust_server_certificate=trust_server_certificate,
                )
            elif auth == AuthType.MICROSOFT_AUTH:
                return from_values_mssql(
                    auth,
                    driver,
                    conn_data[Settings.FileExtraction.server_marker],
                    conn_data[Settings.FileExtraction.database_marker],
                    unique_id=unique_id,
                    api=api,
                    encrypt=encrypt,
                    trust_server_certificate=trust_server_certificate,
                )
            else:
                raise ValueError(f"'{auth}' is not a supported authentication method")

        case DialectTypes.MYSQL:
            return from_values_mysql()

        case DialectTypes.POSTGRESQL:
            return from_values_postgresql()

        case DialectTypes.MARIADB:
            return from_values_mariadb()

        case DialectTypes.SQLITE:
            return from_values_sqlite()

        case DialectTypes.ORACLE:
            return from_values_oracle()

@overload
def from_values_mssql(
    auth_type: Literal[AuthType.MICROSOFT_AUTH],
    driver: _driver_types.SqlServerDrivers,
    server: str,
    database: str,
    *,
    unique_id: Optional[str] = None,
    api: SqlServerApi = SqlServerApi.PYODBC,
    encrypt: Optional[bool] = None,
    trust_server_certificate: Optional[bool] = None,
) -> ConnectionInfo: ...
@overload
def from_values_mssql(
    auth_type: Literal[AuthType.SQL_AUTH],
    driver: _driver_types.SqlServerDrivers,
    server: str,
    database: str,
    *,
    user_name: str,
    user_pwd: SecretStr,
    unique_id: Optional[str] = None,
    api: SqlServerApi = SqlServerApi.PYODBC,
    encrypt: Optional[bool] = None,
    trust_server_certificate: Optional[bool] = None,
) -> ConnectionInfo: ...

def from_values_mssql(
    auth_type: AuthType,
    driver: _driver_types.SqlServerDrivers,
    server: str,
    database: str,
    *,
    user_name: Optional[str] = None,
    user_pwd: Optional[SecretStr] = None,
    unique_id: Optional[str] = None,
    api: SqlServerApi = SqlServerApi.PYODBC,
    encrypt: Optional[bool] = None,
    trust_server_certificate: Optional[bool] = None,
) -> ConnectionInfo:
    """Build a SQL Server connection from individual values.

    Constructs the SQLAlchemy URL for the chosen auth method and API/driver.
    SQL authentication requires ``user_name`` and ``user_pwd``; Microsoft
    (integrated/Azure AD) authentication does not.

    Args:
        auth_type: Authentication method.
        driver: The SQL Server driver to use.
        server: Server host (and optional instance/port).
        database: Target database name.
        user_name: Login name, required for ``SQL_AUTH``.
        user_pwd: Login password, required for ``SQL_AUTH``.
        unique_id: Optional identifier for the connection; a random one is
            generated when ``None``.
        api: Python DBAPI used to connect (defaults to PyODBC).

    Returns:
        A ``ConnectionInfo`` for the SQL Server connection.

    Raises:
        ValueError: If ``SQL_AUTH`` is chosen without ``user_name`` and
            ``user_pwd``.
        ImportError: If the DBAPI driver behind ``api`` is not installed.
    """
    require_driver(api, "mssql")

    conn_url: sqlalchemy.URL
    match auth_type:
        case AuthType.SQL_AUTH:
            if user_name is None or user_pwd is None:
                raise ValueError("SQL Authentication needs user_name and 'user_pwd' to be 'passed'")
            conn_url = mssql.sql_auth(
                driver, server, database, user_name, user_pwd, api,
                encrypt, trust_server_certificate,
            )

        case AuthType.MICROSOFT_AUTH:
            conn_url = mssql.microsoft_auth(
                driver, server, database, api,
                encrypt, trust_server_certificate,
            )

    return ConnectionInfo(conn_url, unique_id)

def from_values_mysql() -> ConnectionInfo:
    """Build a MySQL connection from individual values.

    Not yet implemented.

    Raises:
        NotImplementedError: Always, until MySQL support is added.
    """
    raise NotImplementedError("Function not implemented")

def from_values_postgresql() -> ConnectionInfo:
    """Build a PostgreSQL connection from individual values.

    Not yet implemented.

    Raises:
        NotImplementedError: Always, until PostgreSQL support is added.
    """
    raise NotImplementedError("Function not implemented")

def from_values_mariadb() -> ConnectionInfo:
    """Build a MariaDB connection from individual values.

    Not yet implemented.

    Raises:
        NotImplementedError: Always, until MariaDB support is added.
    """
    raise NotImplementedError("Function not implemented")

def from_values_sqlite() -> ConnectionInfo:
    """Build a SQLite connection from individual values.

    Not yet implemented.

    Raises:
        NotImplementedError: Always, until SQLite support is added.
    """
    raise NotImplementedError("Function not implemented")

def from_values_oracle() -> ConnectionInfo:
    """Build an Oracle connection from individual values.

    Not yet implemented.

    Raises:
        NotImplementedError: Always, until Oracle support is added.
    """
    raise NotImplementedError("Function not implemented")

