from pydantic import SecretStr
import sqlalchemy

from ...resources.types import _driver_types
from ..._core.types.api_types import SqlServerApi


def sql_auth(
    driver: _driver_types.SqlServerDrivers,
    server: str,
    database: str,
    user_name: str,
    user_pwd: SecretStr,
    api: SqlServerApi,
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
            }
        )


def microsoft_auth(
    driver: _driver_types.SqlServerDrivers,
    server: str,
    database: str,
    api: SqlServerApi,
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
        }
    )
