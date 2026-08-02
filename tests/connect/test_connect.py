from pathlib import Path

import pytest
import sqlalchemy
from pydantic import SecretStr

from alchemy_kit.connect import EngineManager, ConnectionInfo
from alchemy_kit.connect.info_builder import (
    from_env,
    from_json,
    from_values_mssql,
)
from alchemy_kit.resources.dialects import MssqlMap, SqliteMap
from alchemy_kit.types.auth_types import AuthType
from alchemy_kit.types._driver_types import SqlServerNative, SqlServerODBC

DIR = Path(__file__).resolve().parent.parent

def test_init_info():
    a = from_json(DIR / "test_json.json")
    assert a.unique_id == "test"

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

def test_named_json_entry_is_the_one_built():
    con = from_json(DIR / "test_json_multi.json", "second", expect=MssqlMap)

    assert con.unique_id == "second"
    assert "second_database" in str(con.con_url)


def test_json_siblings_are_left_unbuilt():
    con = from_json(DIR / "test_json_multi.json", "first")

    assert con.unique_id == "first"


def test_json_entry_must_be_named_when_the_file_holds_several():
    with pytest.raises(ValueError, match="pass one of"):
        from_json(DIR / "test_json_multi.json")


def test_unknown_json_entry_is_rejected():
    with pytest.raises(ValueError, match="'absent' is not in"):
        from_json(DIR / "test_json_multi.json", "absent")


def test_manager():
    url = sqlalchemy.URL.create("sqlite")
    info = ConnectionInfo(url, "a")

    with EngineManager(None) as manager:
        handler = manager.create_handler(info)
        assert handler.get_connection_info().unique_id == "a"




def test_engine_kwargs_enable_fast_executemany_for_pyodbc():
    explicit = ConnectionInfo(sqlalchemy.make_url("mssql+pyodbc://"))
    default_driver = ConnectionInfo(sqlalchemy.make_url("mssql://"))

    assert explicit.engine_kwargs() == {"fast_executemany": True}
    assert default_driver.engine_kwargs() == {"fast_executemany": True}


def test_engine_kwargs_are_empty_for_drivers_that_batch_natively():
    for url in ("mssql+pymssql://", "postgresql+psycopg://", "oracle+oracledb://", "sqlite://"):
        assert ConnectionInfo(sqlalchemy.make_url(url)).engine_kwargs() == {}


def test_expected_dialect_is_accepted():
    info = ConnectionInfo(sqlalchemy.make_url("sqlite://"), expect=SqliteMap)

    assert from_env(DIR / "dotenv_test", expect=MssqlMap).dialect is MssqlMap
    assert from_json(DIR / "test_json.json", expect=MssqlMap)
    assert info.dialect is SqliteMap


def test_unexpected_dialect_is_rejected():
    with pytest.raises(ValueError):
        ConnectionInfo(sqlalchemy.make_url("sqlite://"), expect=MssqlMap)

    with pytest.raises(ValueError):
        from_env(DIR / "dotenv_test", expect=SqliteMap)

    with pytest.raises(ValueError):
        from_json(DIR / "test_json.json", expect=SqliteMap)


def test_pooled_handler_is_rejected_for_another_dialect():
    info = ConnectionInfo(sqlalchemy.URL.create("sqlite"), "b")

    with EngineManager(None) as manager:
        manager.create_handler(info)

        assert manager.get_handler("b", SqliteMap).get_connection_info().dialect is SqliteMap
        with pytest.raises(ValueError):
            manager.get_handler("b", MssqlMap)


