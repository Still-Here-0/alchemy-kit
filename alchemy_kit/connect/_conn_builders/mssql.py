from typing import Optional

from pydantic import SecretStr
import sqlalchemy

from ...types import _driver_types
from ...types.api_types import SqlServerApi


def _tls_query(
    encrypt: Optional[bool],
    trust_server_certificate: Optional[bool],
) -> dict[str, str]:
    query: dict[str, str] = {}
    if encrypt is not None:
        query["Encrypt"] = "yes" if encrypt else "no"
    if trust_server_certificate is not None:
        query["TrustServerCertificate"] = "yes" if trust_server_certificate else "no"
    return query


def sql_auth(
    driver: _driver_types.SqlServerDrivers,
    server: str,
    database: str,
    user_name: str,
    user_pwd: SecretStr,
    api: SqlServerApi,
    encrypt: Optional[bool] = None,
    trust_server_certificate: Optional[bool] = None,
) -> sqlalchemy.URL:

    if isinstance(driver, _driver_types.SqlServerODBC):
        return sqlalchemy.URL.create(
            drivername=f"mssql+{api}",
            username=user_name,
            password=user_pwd.get_secret_value(),
            host=server,
            database=database,
            query={
                "driver": driver,
                "ApplicationIntent": "ReadWrite",
                "MultiSubnetFailover": "yes",
                **_tls_query(encrypt, trust_server_certificate),
            }
        )

    if isinstance(driver, _driver_types.SqlServerNative):
        return sqlalchemy.URL.create(
            drivername=f"mssql+{api}",
            username=user_name,
            password=user_pwd.get_secret_value(),
            host=server,
            database=database,
            query={
                "driver": driver,
                **_tls_query(encrypt, trust_server_certificate),
            }
        )


def microsoft_auth(
    driver: _driver_types.SqlServerDrivers,
    server: str,
    database: str,
    api: SqlServerApi,
    encrypt: Optional[bool] = None,
    trust_server_certificate: Optional[bool] = None,
) -> sqlalchemy.URL:
    return sqlalchemy.URL.create(
        drivername=f"mssql+{api}",
        host=server,
        database=database,
        query={
            "driver": driver,
            "Trusted_Connection": "yes",
            "ApplicationIntent": "ReadWrite",
            "MultiSubnetFailover": "yes",
            **_tls_query(encrypt, trust_server_certificate),
        }
    )
