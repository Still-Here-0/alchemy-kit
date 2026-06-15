from typing import overload, cast, Optional, Dict
from dotenv import dotenv_values
from pydantic import SecretStr
from pathlib import Path
import sqlalchemy
import json

from .._core.types import driver_types, auth_types, GenericPath, DialectTypes
from .._core.types.api_types import SqlServerApi
from .._core.types.utils import check_literal
from ._conn_builders import mssql
from ._info import ConnectionInfo


def from_json(json_path: GenericPath) -> Dict[str, ConnectionInfo]:
    json_path = Path(json_path).resolve()
    connections = {}
    
    with json_path.open('r', encoding="UTF-8") as file:
        data: Dict[str, Dict[str, str]] = json.load(file)

        for unique_id, conn_data in data.items():
            dialect: str = conn_data["dialect"]
            if not check_literal(dialect, DialectTypes):
                raise ValueError(f"'{dialect}' is not a supported dialect, URLs that use those types of drivers should be built by the user with 'info_builder.from_url'")

            connections[unique_id] = _match_dialect(cast(DialectTypes, dialect), conn_data)

    return connections

def from_env(env_path: GenericPath) -> ConnectionInfo: 
    env_path = Path(env_path).resolve()
    env_data = cast(Dict[str, str], dotenv_values(env_path))
    dialect = env_data["dialect"]

    if check_literal(dialect, DialectTypes):
        return _match_dialect(cast(DialectTypes, dialect), env_data)
    
    raise ValueError(f"'{dialect}' is not a supported dialect")

def _match_dialect(dialect: DialectTypes, conn_data: Dict[str, str]) -> ConnectionInfo:
    auth = conn_data["auth"]
    if not check_literal(auth, auth_types.AuthType):
        raise ValueError(f"No authentication type called: {auth_types}")
    auth = cast(auth_types.AuthType, auth)
    match dialect:
        case "mssql":
            driver = conn_data["driver"]
            api = conn_data["api"]
            if not check_literal(driver, driver_types.SqlServerDrivers):
                raise ValueError(f"'{driver}' not a supported driver")

            if not check_literal(api, SqlServerApi):
                raise ValueError(f"'{api}' not a supported api")
            
            if check_literal(auth, auth_types.SqlAuth):
                return from_values_mssql(
                    cast(auth_types.SqlAuth, auth),
                    cast(driver_types.SqlServerDrivers, driver),
                    conn_data["server"],
                    conn_data["database"],
                    user_name=conn_data["user_name"],
                    user_pwd=SecretStr(conn_data["user_pwd"]),
                    unique_id=conn_data["a"],
                    api=cast(SqlServerApi, api)
                )
            elif check_literal(auth, auth_types.MicrosoftAuth):
                return from_values_mssql(
                    cast(auth_types.MicrosoftAuth, auth),
                    cast(driver_types.SqlServerDrivers, driver),
                    conn_data["server"],
                    conn_data["database"],
                    unique_id=conn_data["a"],
                    api=cast(SqlServerApi, api)
                )
            else:
                raise ValueError("'auth' is not a supported authentication method")

        case "mysql":
            return from_values_mysql()

        case "postgesql":
            return from_values_postgresql()

        case "mariadb":
            return from_values_mariadb()

        case "sqlite":
            return from_values_sqlite()

        case "oracle":
            return from_values_oracle()

def from_url(url: sqlalchemy.URL, unique_id: Optional[str] = None) -> ConnectionInfo:
    return ConnectionInfo(url, unique_id)

@overload
def from_values_mssql(
    auth_type: auth_types.MicrosoftAuth,
    driver: driver_types.SqlServerDrivers,
    server: str,
    database: str,
    *,
    unique_id: Optional[str] = None,
    api: SqlServerApi = "pyodbc",
) -> ConnectionInfo: ...
@overload
def from_values_mssql(
    auth_type: auth_types.SqlAuth,
    driver: driver_types.SqlServerDrivers,
    server: str,
    database: str,
    *,
    user_name: str,
    user_pwd: SecretStr,
    unique_id: Optional[str] = None,
    api: SqlServerApi = "pyodbc",
) -> ConnectionInfo: ...

def from_values_mssql(
    auth_type: auth_types.AuthType,
    driver: driver_types.SqlServerDrivers,
    server: str,
    database: str,
    *,
    user_name: Optional[str] = None,
    user_pwd: Optional[SecretStr] = None,
    unique_id: Optional[str] = None,
    api: SqlServerApi = "pyodbc",
) -> ConnectionInfo:
    conn_url: sqlalchemy.URL
    match auth_type:
        case auth_types.SqlAuth:
            if user_name is None or user_pwd is None:
                raise ValueError("SQL Authentication needs user_name and user_pwd to be passed")
            conn_url = mssql.sql_auth(driver, server, database, user_name, user_pwd, api)

        case auth_types.MicrosoftAuth:
            conn_url = mssql.microsoft_auth(driver, server, database, api)

        case _:
            raise ValueError(f"No authentication type called: {auth_types}")

    return ConnectionInfo(conn_url, unique_id)

def from_values_mysql() -> ConnectionInfo:
    raise NotImplementedError("Function not implemented")

def from_values_postgresql() -> ConnectionInfo:
    raise NotImplementedError("Function not implemented")

def from_values_mariadb() -> ConnectionInfo:
    raise NotImplementedError("Function not implemented")

def from_values_sqlite() -> ConnectionInfo:
    raise NotImplementedError("Function not implemented")

def from_values_oracle() -> ConnectionInfo:
    raise NotImplementedError("Function not implemented")

