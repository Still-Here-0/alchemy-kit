from pathlib import Path

import sqlalchemy
from pydantic import SecretStr

from alchemy_kit.connect.info_builder import (
    from_env,
    from_json,
    from_url,
    from_values_mssql,
)
from alchemy_kit.resources.types import AuthType, SqlServerODBC, SqlServerNative


def test_init_info():
    DIR = Path(__file__).resolve().parent.parent
    a = from_json(DIR / "test_json.json")
    print(f"{a=}")

    b = from_env(DIR / "dotenv_test")
    print("b=" + b.unique_id)

    url = sqlalchemy.URL.create("teste_driver")
    c = from_url(url)
    print("c=" + c.unique_id)

    d = from_values_mssql(
        AuthType.SQL_AUTH,
        SqlServerODBC.DRIVER_11,
        "teste",
        "teste",
        user_name="teste",
        user_pwd=SecretStr("teste"),
    )
    print("d=" + d.unique_id)

    e = from_values_mssql(
        AuthType.MICROSOFT_AUTH, SqlServerNative.CLIENT_11, "teste", "teste"
    )
    print("e=" + e.unique_id)
