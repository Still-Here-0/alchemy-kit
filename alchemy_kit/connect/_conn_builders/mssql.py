from pydantic import SecretStr
import sqlalchemy

from ..._core.types import driver_types
from ..._core.types.utils import check_literal
from ..._core.types.api_types import SqlServerApi


def sql_auth(
    driver: driver_types.SqlServerDrivers,
    server: str,
    database: str,
    user_name: str,
    user_pwd: SecretStr,
    api: SqlServerApi,
) -> sqlalchemy.URL:

    if check_literal(driver, driver_types.SqlServerODBC):
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

    elif check_literal(driver, driver_types.SqlServerNative):
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

    else:
        raise ValueError(f"'{driver}' not supported, URLs that use those types of drivers should be built by the user with 'info_builder.from_url'")


def microsoft_auth(
    driver: driver_types.SqlServerDrivers,
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
