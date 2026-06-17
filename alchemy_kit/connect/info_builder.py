import json
from pathlib import Path
from typing import Dict, Literal, Optional, List, cast, overload

import sqlalchemy
from dotenv import dotenv_values
from pydantic import SecretStr

from .._core.types import DialectTypes, GenericPath, api_types
from .._core.types.api_types import SqlServerApi
from ..resources.types import AuthType, _driver_types
from ._conn_builders import mssql
from ._info import ConnectionInfo


def from_json(json_path: GenericPath) -> List[ConnectionInfo]:
    json_path = Path(json_path).resolve()
    connections = {}
    
    with json_path.open('r', encoding="UTF-8") as file:
        data: Dict[str, Dict[str, str]] = json.load(file)

        for unique_id, conn_data in data.items():
            dialect = DialectTypes(conn_data["dialect"])
            connections[unique_id] = _match_dialect(cast(DialectTypes, dialect), unique_id, conn_data)
            
    return list(connections.values())

def from_env(env_path: GenericPath) -> ConnectionInfo: 
    env_path = Path(env_path).resolve()
    env_data = cast(Dict[str, str], dotenv_values(env_path))
    dialect = DialectTypes(env_data["dialect"])

    return _match_dialect(cast(DialectTypes, dialect), env_data.get("unique_id"), env_data)

def _match_dialect(dialect: DialectTypes, unique_id: Optional[str], conn_data: Dict[str, str]) -> ConnectionInfo: # CONTINUE
    auth = AuthType(conn_data["auth"])
    
    match dialect:
        case DialectTypes.MSSQL:
            driver = _driver_types.parse_sql_server_driver(conn_data["driver"])
            api = api_types.SqlServerApi(conn_data.get("api", api_types.SqlServerApi.PYODBC))

            if auth == AuthType.SQL_AUTH:
                return from_values_mssql(
                    auth,
                    driver,
                    conn_data["server"],
                    conn_data["database"],
                    user_name=conn_data["user_name"],
                    user_pwd=SecretStr(conn_data["user_pwd"]),
                    unique_id=unique_id,
                    api=cast(SqlServerApi, api)
                )
            elif auth == AuthType.MICROSOFT_AUTH:
                return from_values_mssql(
                    auth,
                    driver,
                    conn_data["server"],
                    conn_data["database"],
                    unique_id=unique_id,
                    api=api
                )
            else:
                raise ValueError("'auth' is not a supported authentication method")

        case DialectTypes.MYSQL:
            return from_values_mysql()

        case DialectTypes.POSTGESQL:
            return from_values_postgresql()

        case DialectTypes.MARIADB:
            return from_values_mariadb()

        case DialectTypes.SQLITE:
            return from_values_sqlite()

        case DialectTypes.ORACLE:
            return from_values_oracle()

def from_url(url: sqlalchemy.URL, unique_id: Optional[str] = None) -> ConnectionInfo:
    return ConnectionInfo(url, unique_id)

@overload
def from_values_mssql(
    auth_type: Literal[AuthType.MICROSOFT_AUTH],
    driver: _driver_types.SqlServerDrivers,
    server: str,
    database: str,
    *,
    unique_id: Optional[str] = None,
    api: SqlServerApi = SqlServerApi.PYODBC,
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
) -> ConnectionInfo:
    conn_url: sqlalchemy.URL
    match auth_type:
        case AuthType.SQL_AUTH:
            if user_name is None or user_pwd is None:
                raise ValueError("SQL Authentication needs user_name and 'user_pwd' to be 'passed'")
            conn_url = mssql.sql_auth(driver, server, database, user_name, user_pwd, api)

        case AuthType.MICROSOFT_AUTH:
            conn_url = mssql.microsoft_auth(driver, server, database, api)

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

