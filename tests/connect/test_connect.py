from pathlib import Path

import sqlalchemy
from pydantic import SecretStr

from alchemy_kit.connect import EngineManager, ConnectionInfo
from alchemy_kit.connect.info_builder import (
    from_env,
    from_json,
    from_values_mssql,
)
from alchemy_kit.types.auth_types import AuthType
from alchemy_kit.types._driver_types import SqlServerNative, SqlServerODBC

DIR = Path(__file__).resolve().parent.parent

def test_init_info():
    a = from_json(DIR / "test_json.json")
    assert all([isinstance(con.unique_id, str) for con in a])

    b = from_env(DIR / "dotenv_test")
    assert isinstance(b.unique_id, str)

    url = sqlalchemy.URL.create("mssql")
    c = ConnectionInfo(url)
    assert isinstance(c.unique_id, str)

    d = from_values_mssql(
        AuthType.SQL_AUTH,
        SqlServerODBC.DRIVER_11,
        "teste",
        "teste",
        user_name="teste",
        user_pwd=SecretStr("teste"),
        unique_id="a"
    )
    assert d.unique_id == "a"

    e = from_values_mssql(
        AuthType.MICROSOFT_AUTH, SqlServerNative.CLIENT_11, "teste", "teste"
    )
    assert isinstance(e.unique_id, str)

def test_manager():
    url = sqlalchemy.URL.create("sqlite")
    info = ConnectionInfo(url, "a")

    with EngineManager(None) as manager:
        handler = manager.create_engine(info)
        assert handler._con_info.unique_id == "a"


