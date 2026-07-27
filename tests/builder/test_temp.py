import pandas as pd
import pytest
import sqlalchemy

from alchemy_kit.builder import InsertBuilder, SelectBuilder, TempBuilder
from alchemy_kit.builder._utils import DataFrameTemp
from alchemy_kit.connect._engine_handler import EngineHandler
from alchemy_kit.resources._sql import SQL

from _helpers import MSSQL_HANDLER, SQLITE_HANDLER, items, mssql_items


def test_temp_round_trip_through_run_sql(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    assert 'CREATE TEMPORARY TABLE "TEMP_items"' in tmp.render()
    tmp.run()

    t = tmp.unit()
    InsertBuilder(t).from_values((t.id_1, 1), (t.name, "bolt"), (t.price, 0.5)).run()
    InsertBuilder(t).from_values((t.id_1, 2), (t.name, "nut"), (t.price, 1.5)).run()
    InsertBuilder(t).from_values((t.id_1, 3), (t.name, "gear"), (t.price, 9.0)).run()

    _, df = SelectBuilder(t.name, t.price, from_=t).where(t.price > 1).order_by(t.price.desc()).run()
    assert df["name"].tolist() == ["gear", "nut"]

    handler.run_sql(SQL(raw_query="CREATE TABLE main.items (id INTEGER NOT NULL, name VARCHAR NOT NULL, price REAL)"))
    moved, _ = (
        InsertBuilder(handler.get_unit(items))
        .from_select(SelectBuilder(t.id_1, t.name, t.price, from_=t).where(t.price > 1))
        .run()
    )
    assert moved == 2

    _, real = SelectBuilder(from_=handler.get_unit(items)).run()
    assert sorted(real["name"].tolist()) == ["gear", "nut"]


def test_global_temp_rejected_on_unsupported_dialect():
    with pytest.raises(ValueError):
        TempBuilder(SQLITE_HANDLER.get_unit(items), global_temp=True)


def test_mssql_temp_naming():
    assert "[#TEMP_items]" in TempBuilder(MSSQL_HANDLER.get_unit(mssql_items)).render()
    assert "[##TEMP_items]" in TempBuilder(MSSQL_HANDLER.get_unit(mssql_items), global_temp=True).render()


def test_from_dataframe_infers_column_types():
    df = pd.DataFrame({
        "flag": [True, False],
        "count": [1, 2],
        "price": [0.5, 1.5],
        "moment": pd.to_datetime(["2024-01-01", "2024-02-01"]),
        "span": pd.to_timedelta([1, 2], unit="D"),
        "label": ["bolt", "a-much-longer-label"],
        "blank": [None, None],
    })
    builder = TempBuilder.from_dataframe(df, SQLITE_HANDLER, "stuff")

    types = {c.name: type(c.type) for c in builder._table.columns}
    assert types == {
        "flag": sqlalchemy.Boolean,
        "count": sqlalchemy.BigInteger,
        "price": sqlalchemy.Float,
        "moment": sqlalchemy.DateTime,
        "span": sqlalchemy.Interval,
        "label": sqlalchemy.String,
        "blank": sqlalchemy.String,
    }

    rendered = builder.render()
    assert 'CREATE TEMPORARY TABLE "TEMP_stuff"' in rendered
    assert "label VARCHAR(19)" in rendered
    assert "blank VARCHAR(1)" in rendered


def test_from_dataframe_infers_schema_without_rows():
    df = pd.DataFrame({"id": pd.Series(dtype="int64"), "name": pd.Series(dtype="object")})
    rendered = TempBuilder.from_dataframe(df, SQLITE_HANDLER, "empty").render()

    assert "id BIGINT" in rendered
    assert "name VARCHAR(1)" in rendered


def test_from_dataframe_stringifies_column_labels():
    builder = TempBuilder.from_dataframe(pd.DataFrame([[1, 2]]), SQLITE_HANDLER, "nums")
    assert [c.name for c in builder._table.columns] == ["0", "1"]


def test_from_dataframe_round_trip(handler: EngineHandler):
    df = pd.DataFrame([
        {"a": 1, "b": "bolt", "c": 0.5},
        {"a": 2, "b": "nut", "c": 1.5},
    ])
    tmp = TempBuilder.from_dataframe(df, handler, "raw")
    tmp.run()

    t = tmp.unit()
    InsertBuilder(t).from_dataframe(df).run()

    _, out = SelectBuilder(t.a, t.b, t.c, from_=t).where(t.c > 1).run()
    assert out["b"].tolist() == ["nut"]
    assert out["a"].tolist() == [2]


def test_from_dataframe_base_resolves_model_field_names(handler: EngineHandler):
    df = pd.DataFrame([
        {"id": 1, "name": "bolt", "price": 0.5},
        {"id": 2, "name": "nut", "price": 1.5},
    ])
    tmp = TempBuilder.from_dataframe(df, handler, "items", base=items)
    assert 'CREATE TEMPORARY TABLE "TEMP_items"' in tmp.render()
    tmp.run()

    t = tmp.unit()
    InsertBuilder(t).from_dataframe(df).run()

    _, out = SelectBuilder(t.name, t.price, from_=t).where(t.price > 1).order_by(t.id_1).run()
    assert out["name"].tolist() == ["nut"]


def test_from_dataframe_default_base_uses_raw_column_names(handler: EngineHandler):
    tmp = TempBuilder.from_dataframe(pd.DataFrame([{"id": 1}]), handler, "raw")

    assert tmp.unit()._base is DataFrameTemp
    with pytest.raises(AttributeError):
        tmp.unit().id_1


def test_from_dataframe_mssql_naming():
    df = pd.DataFrame([{"id": 1}])
    assert "[#TEMP_stuff]" in TempBuilder.from_dataframe(df, MSSQL_HANDLER, "stuff").render()
    assert "[##TEMP_stuff]" in TempBuilder.from_dataframe(
        df, MSSQL_HANDLER, "stuff", global_temp=True
    ).render()


def test_from_dataframe_global_temp_rejected_on_unsupported_dialect():
    with pytest.raises(ValueError):
        TempBuilder.from_dataframe(
            pd.DataFrame([{"id": 1}]), SQLITE_HANDLER, "stuff", global_temp=True
        )
