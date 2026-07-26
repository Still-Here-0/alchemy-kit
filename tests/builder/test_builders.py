from typing import Any, Optional, cast

import pandas as pd
import pandera.pandas as pa
import pytest
import sqlalchemy
from pandera.typing import Series

from alchemy_kit.builder import InsertBuilder, SelectBuilder, TempBuilder
from alchemy_kit.builder._utils import DataFrameTemp
from alchemy_kit.connect._engine_handler import EngineHandler
from alchemy_kit.connect._info import ConnectionInfo
from alchemy_kit.model.base_model import BaseModel, MetaData
from alchemy_kit.model.units import OperandUnit
from alchemy_kit.resources._sql import SQL
from alchemy_kit.resources.dialect_map import get_sa_dialect
from alchemy_kit.types.dialect_types import DialectTypes
from alchemy_kit.types.sql_type_parameters import MssqlTypeParameters, SqliteTypeParameters


class items(BaseModel[SqliteTypeParameters]):
    id_1: Series[int] = pa.Field(nullable=False, alias="id", metadata={"original_type": "integer"})
    name: Series[str] = pa.Field(nullable=False, alias="name", metadata={"original_type": "varchar"})
    price: Optional[Series[float]] = pa.Field(nullable=True, alias="price", metadata={"original_type": "real"})

    class Config(BaseModel.Config):
        metadata = MetaData(
            schema_name="main", obj_name="items", obj_type="Table",
            reference_name='"main"."items"', description=None,
        )


class parts(BaseModel[SqliteTypeParameters]):
    id_1: Series[int] = pa.Field(nullable=False, alias="id", metadata={"original_type": "integer"})
    label: Series[str] = pa.Field(nullable=False, alias="label", metadata={"original_type": "varchar"})

    class Config(BaseModel.Config):
        metadata = MetaData(
            schema_name="main", obj_name="parts", obj_type="Table",
            reference_name='"main"."parts"', description=None,
        )


class mssql_items(BaseModel[MssqlTypeParameters]):
    id_1: Series[int] = pa.Field(nullable=False, alias="id", metadata={"original_type": "int"})

    class Config(BaseModel.Config):
        metadata = MetaData(
            schema_name="dbo", obj_name="items", obj_type="Table",
            reference_name="[dbo].[items]", description=None,
        )


SQLITE_HANDLER = EngineHandler(cast(Any, None), ConnectionInfo(sqlalchemy.make_url("sqlite://")))
MSSQL_HANDLER = EngineHandler(cast(Any, None), ConnectionInfo(sqlalchemy.make_url("mssql+pyodbc://")))


@pytest.fixture
def handler():
    engine = sqlalchemy.create_engine("sqlite://")
    return EngineHandler(engine, ConnectionInfo(sqlalchemy.make_url("sqlite://")))


def test_every_dialect_compiles_with_named_paramstyle():
    for dialect in DialectTypes:
        assert get_sa_dialect(dialect).paramstyle == "named"


def test_select_render_and_parameters():
    i = SQLITE_HANDLER.get_unit(items)
    builder = (
        SelectBuilder(i.name, i.price.sum().set_alias("total"), from_=i)
        .where(i.price > 1)
        .group_by(i.name)
        .having(i.price.sum() > 2)
        .order_by(i.price.sum().desc())
        .limit(5)
    )
    rendered = builder.render()

    assert "GROUP BY" in rendered and "HAVING" in rendered and "ORDER BY" in rendered

    parameters = builder.to_sql().query_parameters
    assert isinstance(parameters, dict)
    assert parameters.items() >= {"price_1": 1, "sum_1": 2, "param_1": 5}.items()


def test_select_builder_is_immutable():
    i = SQLITE_HANDLER.get_unit(items)
    base = SelectBuilder(i.name, from_=i)
    filtered = base.where(i.price > 1)

    assert "WHERE" not in base.render()
    assert "WHERE" in filtered.render()


def test_mixing_engine_handlers_raises(handler: EngineHandler):
    i = handler.get_unit(items)
    o = SQLITE_HANDLER.get_unit(items)

    with pytest.raises(ValueError):
        SelectBuilder(i.name, o.id_1, from_=i)
    with pytest.raises(ValueError):
        SelectBuilder(i.name, from_=i).where(o.price > 1)
    with pytest.raises(ValueError):
        SelectBuilder(i.name, from_=i).order_by(o.price.desc())
    with pytest.raises(ValueError):
        InsertBuilder(handler.get_unit(items)).from_select(SelectBuilder(o.id_1, from_=o))


def test_cross_join_compiles_and_runs(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values(id_1=1, name="bolt", price=0.5).run()
    InsertBuilder(t).from_values(id_1=2, name="nut", price=1.5).run()

    o = tmp.unit().set_alias("o")
    builder = SelectBuilder(t.name, o.price, from_=t).join("CROSS", o)
    assert "ON 1 = 1" in builder.render()

    _, df = builder.run()
    assert len(df) == 4


def test_right_join_keeps_unmatched_right_rows(handler: EngineHandler):
    items_tmp = TempBuilder(handler.get_unit(items))
    items_tmp.run()
    parts_tmp = TempBuilder(handler.get_unit(parts))
    parts_tmp.run()

    t, p = items_tmp.unit(), parts_tmp.unit()
    InsertBuilder(t).from_values(id_1=1, name="bolt", price=0.5).run()
    InsertBuilder(p).from_values(id_1=1, label="washer").run()
    InsertBuilder(p).from_values(id_1=2, label="nut").run()

    builder = SelectBuilder(t.name, p.id_1, from_=t).join("RIGHT", p, t.id_1 == p.id_1)
    assert "LEFT OUTER JOIN" in builder.render()

    _, df = builder.run()
    assert sorted(df["id"].tolist()) == [1, 2]
    assert df["name"].isna().sum() == 1


def test_joins_chain_after_right(handler: EngineHandler):
    items_tmp = TempBuilder(handler.get_unit(items))
    items_tmp.run()
    parts_tmp = TempBuilder(handler.get_unit(parts))
    parts_tmp.run()

    t, p = items_tmp.unit(), parts_tmp.unit()
    InsertBuilder(t).from_values(id_1=1, name="bolt", price=0.5).run()
    InsertBuilder(p).from_values(id_1=1, label="washer").run()
    InsertBuilder(p).from_values(id_1=2, label="nut").run()

    third = parts_tmp.unit().set_alias("third")
    builder = (
        SelectBuilder(t.name, p.id_1, from_=t)
        .join("RIGHT", p, t.id_1 == p.id_1)
        .join("INNER", third, p.id_1 == third.id_1)
    )
    rendered = builder.render()
    assert rendered.count("JOIN") == 2

    _, df = builder.run()
    assert sorted(df["id"].tolist()) == [1, 2]


def test_join_condition_arity():
    i = SQLITE_HANDLER.get_unit(items)
    o = SQLITE_HANDLER.get_unit(items).set_alias("o")
    with pytest.raises(TypeError):
        SelectBuilder(i.name, from_=i).join("CROSS", o, i.id_1 == o.id_1)
    with pytest.raises(TypeError):
        SelectBuilder(i.name, from_=i).join("INNER", o)


def test_insert_to_sqls_chunks_and_runs_with_temp_table(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    insert = InsertBuilder(tmp.unit()).from_dataframe(pd.DataFrame([
        {"id_1": 1, "name": "bolt", "price": 0.5},
        {"id_1": 2, "name": "nut", "price": 1.5},
        {"id_1": 3, "name": "gear", "price": 9.0},
    ]))

    insert_sqls = insert.to_sqls(chunk_size=2)
    assert len(insert_sqls) == 2

    results = handler.run_sqls([
        tmp.to_sql(),
        *insert_sqls,
        SelectBuilder(tmp.unit().name, from_=tmp.unit()).to_sql(),
    ])

    assert sorted(results[-1][1]["name"].tolist()) == ["bolt", "gear", "nut"]

def test_insert_run_uses_to_sqls_and_aggregates_chunks(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    insert = InsertBuilder(tmp.unit()).from_dataframe(pd.DataFrame([
        {"id_1": 1, "name": "bolt", "price": 0.5},
        {"id_1": 2, "name": "nut", "price": 1.5},
        {"id_1": 3, "name": "gear", "price": 9.0},
    ]))

    count, data = insert.run(chunk_size=2)

    assert count == 3
    assert data.empty


def test_insert_rejects_aliased_unit():
    with pytest.raises(TypeError):
        InsertBuilder(SQLITE_HANDLER.get_unit(items).set_alias("x"))


def test_temp_round_trip_through_run_sql(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    assert 'CREATE TEMPORARY TABLE "TEMP_items"' in tmp.render()
    tmp.run()

    t = tmp.unit()
    for row in [
        dict(id_1=1, name="bolt", price=0.5),
        dict(id_1=2, name="nut", price=1.5),
        dict(id_1=3, name="gear", price=9.0),
    ]:
        InsertBuilder(t).from_values(**row).run()

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


def test_null_safe_comparisons(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values(id_1=1, name="bolt", price=0.5).run()
    InsertBuilder(t).from_values(id_1=2, name="nut", price=None).run()

    _, df = SelectBuilder(t.name, from_=t).where(t.price != 0.5).run()
    assert df["name"].tolist() == []

    _, df = SelectBuilder(t.name, from_=t).where(t.price.is_distinct_from(0.5)).run()
    assert df["name"].tolist() == ["nut"]

    _, df = SelectBuilder(t.name, from_=t).where(t.price.is_not_distinct_from(None)).run()
    assert df["name"].tolist() == ["nut"]


def test_nullif_guards_division(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values(id_1=1, name="free", price=0.0).run()
    InsertBuilder(t).from_values(id_1=2, name="dear", price=2.0).run()

    _, df = SelectBuilder(t.name, (10 / t.price.nullif(0)).set_alias("ratio"), from_=t).run()
    by_name = dict(zip(df["name"], df["ratio"]))
    assert by_name["free"] is None or by_name["free"] != by_name["free"]
    assert by_name["dear"] == 5.0


def test_floor_division(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values(id_1=7, name="bolt", price=4.5).run()

    builder = SelectBuilder((t.id_1 // 2).set_alias("half"), (100 // t.id_1).set_alias("inverse"), (t.price // 2).set_alias("floored"), from_=t)
    assert "FLOOR" in builder.render()

    _, df = builder.run()
    assert df["half"].tolist() == [3]
    assert df["inverse"].tolist() == [14]
    assert df["floored"].tolist() == [2.0]


def test_string_operations(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values(id_1=1, name="  Bolt  ", price=0.5).run()

    _, df = SelectBuilder(t.name.trim().lower().set_alias("clean"), t.name.trim().upper().set_alias("loud"), t.name.trim().length().set_alias("size"), t.name.trim().concat("-", t.name.trim()).set_alias("doubled"), from_=t).run()

    assert df["clean"].tolist() == ["bolt"]
    assert df["loud"].tolist() == ["BOLT"]
    assert df["size"].tolist() == [4]
    assert df["doubled"].tolist() == ["Bolt-Bolt"]


def test_ordering_unit_null_placement(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values(id_1=1, name="bolt", price=9.0).run()
    InsertBuilder(t).from_values(id_1=2, name="nut", price=None).run()
    InsertBuilder(t).from_values(id_1=3, name="gear", price=0.5).run()

    builder = SelectBuilder(t.name, from_=t).order_by(t.price.desc().nulls_last())
    assert "NULLS LAST" in builder.render()

    _, df = builder.run()
    assert df["name"].tolist() == ["bolt", "gear", "nut"]

    _, df = SelectBuilder(t.name, from_=t).order_by(t.price.asc().nulls_first()).run()
    assert df["name"].tolist() == ["nut", "gear", "bolt"]


def test_ordering_unit_is_not_a_value():
    i = SQLITE_HANDLER.get_unit(items)
    with pytest.raises(TypeError):
        _ = i.price.desc() + 1  # pyright: ignore[reportOperatorIssue]
    with pytest.raises(AttributeError):
        i.price.desc().sum()  # pyright: ignore[reportAttributeAccessIssue]


def test_window_running_total(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values(id_1=1, name="bolt", price=10.0).run()
    InsertBuilder(t).from_values(id_1=2, name="nut", price=25.0).run()
    InsertBuilder(t).from_values(id_1=3, name="gear", price=5.0).run()

    builder = SelectBuilder(t.name, t.price.sum().over(order_by=t.id_1.asc()).set_alias("running"), from_=t).order_by(t.id_1)
    assert "OVER (ORDER BY" in builder.render()

    _, df = builder.run()
    assert df["running"].tolist() == [10.0, 35.0, 40.0]


def test_window_partition(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values(id_1=1, name="bolt", price=1.0).run()
    InsertBuilder(t).from_values(id_1=2, name="bolt", price=2.0).run()
    InsertBuilder(t).from_values(id_1=3, name="nut", price=5.0).run()

    builder = SelectBuilder(t.name, (t.price / t.price.sum().over(partition_by=t.name)).set_alias("share"), from_=t).order_by(t.id_1)
    assert "OVER (PARTITION BY" in builder.render()

    _, df = builder.run()
    assert df["share"].tolist() == [1 / 3, 2 / 3, 1.0]


def test_window_row_number_per_group(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values(id_1=1, name="bolt", price=1.0).run()
    InsertBuilder(t).from_values(id_1=2, name="bolt", price=2.0).run()
    InsertBuilder(t).from_values(id_1=3, name="nut", price=5.0).run()

    _, df = SelectBuilder(t.name, OperandUnit.row_number()
        .over(partition_by=t.name, order_by=t.price.desc())
        .set_alias("rn"), from_=t).order_by(t.id_1).run()

    assert df["rn"].tolist() == [2, 1, 1]


def test_operand_rankings(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    for row_id, price in [(1, 10.0), (2, 10.0), (3, 20.0)]:
        InsertBuilder(t).from_values(id_1=row_id, name="bolt", price=price).run()

    _, df = SelectBuilder(t.id_1, OperandUnit.rank().over(order_by=t.price.asc()).set_alias("rnk"), OperandUnit.dense_rank().over(order_by=t.price.asc()).set_alias("dense"), OperandUnit.percent_rank().over(order_by=t.price.asc()).set_alias("pct"), OperandUnit.cume_dist().over(order_by=t.price.asc()).set_alias("cume"), from_=t).order_by(t.id_1).run()

    assert df["rnk"].tolist() == [1, 1, 3]
    assert df["dense"].tolist() == [1, 1, 2]
    assert df["pct"].tolist() == [0.0, 0.0, 1.0]
    assert df["cume"].tolist() == [2 / 3, 2 / 3, 1.0]


def test_operand_ntile(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    for row_id in range(1, 5):
        InsertBuilder(t).from_values(id_1=row_id, name="bolt", price=float(row_id)).run()

    _, df = SelectBuilder(t.id_1, OperandUnit.ntile(2).over(order_by=t.price.asc()).set_alias("bucket"), from_=t).order_by(t.id_1).run()

    assert df["bucket"].tolist() == [1, 1, 2, 2]


def test_operand_count_star_in_first_position(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    for row_id in range(1, 4):
        InsertBuilder(t).from_values(id_1=row_id, name="bolt", price=1.0).run()

    builder = SelectBuilder(OperandUnit.count().over().set_alias("total"), t.name, from_=t).order_by(t.id_1)
    assert "count(*) OVER" in builder.render()

    _, df = builder.run()
    assert df["total"].tolist() == [3, 3, 3]


def test_operand_current_timestamp_is_portable(handler: EngineHandler):
    si = handler.get_unit(items)
    mi = MSSQL_HANDLER.get_unit(mssql_items)
    on_sqlite = SelectBuilder(si.id_1, OperandUnit.current_timestamp().set_alias("now"), from_=si)
    on_mssql = SelectBuilder(mi.id_1, OperandUnit.current_timestamp().set_alias("now"), from_=mi)
    assert "CURRENT_TIMESTAMP" in on_sqlite.render()
    assert "CURRENT_TIMESTAMP" in on_mssql.render()

    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values(id_1=1, name="bolt", price=1.0).run()
    _, df = SelectBuilder(t.id_1, OperandUnit.current_timestamp().set_alias("now"), from_=t).run()
    assert df["now"].notna().all()


def test_operand_current_date_unsupported_on_mssql():
    si = SQLITE_HANDLER.get_unit(items)
    mi = MSSQL_HANDLER.get_unit(mssql_items)
    assert "CURRENT_DATE" in SelectBuilder(si.id_1, OperandUnit.current_date().set_alias("d"), from_=si).render()
    with pytest.raises(ValueError):
        SelectBuilder(mi.id_1, OperandUnit.current_date().set_alias("d"), from_=mi).render()


def test_operand_niladic_dialect_matrix():
    from alchemy_kit.model.units import _operand_unit as ou

    def rendered(element: Any, dialect: DialectTypes) -> str:
        return str(element.compile(dialect=get_sa_dialect(dialect)))

    D = DialectTypes

    assert rendered(ou._CurrentDate(), D.SQLITE) == "CURRENT_DATE"
    with pytest.raises(ValueError):
        rendered(ou._CurrentDate(), D.MSSQL)

    assert rendered(ou._CurrentTime(), D.POSTGRESQL) == "CURRENT_TIME"
    for d in (D.MSSQL, D.ORACLE):
        with pytest.raises(ValueError):
            rendered(ou._CurrentTime(), d)

    assert rendered(ou._CurrentUser(), D.MSSQL) == "CURRENT_USER"
    assert rendered(ou._CurrentUser(), D.ORACLE) == "USER"
    with pytest.raises(ValueError):
        rendered(ou._CurrentUser(), D.SQLITE)

    assert rendered(ou._SessionUser(), D.POSTGRESQL) == "SESSION_USER"
    assert rendered(ou._SessionUser(), D.MYSQL) == "SESSION_USER()"
    for d in (D.SQLITE, D.ORACLE):
        with pytest.raises(ValueError):
            rendered(ou._SessionUser(), d)


def test_window_lag(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values(id_1=1, name="bolt", price=10.0).run()
    InsertBuilder(t).from_values(id_1=2, name="nut", price=25.0).run()

    _, df = SelectBuilder(t.name, (t.price - t.price.lag().over(order_by=t.id_1.asc())).set_alias("change"), t.price.lag(1, default=0.0).over(order_by=t.id_1.asc()).set_alias("previous"), from_=t).order_by(t.id_1).run()

    assert df["change"].isna().tolist() == [True, False]
    assert df["change"].tolist()[1] == 15.0
    assert df["previous"].tolist() == [0.0, 10.0]


def test_window_frame(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    for row_id, price in [(1, 2.0), (2, 4.0), (3, 12.0)]:
        InsertBuilder(t).from_values(id_1=row_id, name="bolt", price=price).run()

    builder = SelectBuilder(t.price.avg().over(order_by=t.id_1.asc(), rows=(-1, 0)).set_alias("moving"), from_=t).order_by(t.id_1)
    assert "PRECEDING AND CURRENT ROW" in builder.render()

    _, df = builder.run()
    assert df["moving"].tolist() == [2.0, 3.0, 8.0]


def test_window_function_unit_is_not_a_value():
    i = SQLITE_HANDLER.get_unit(items)
    pending = OperandUnit.row_number()
    with pytest.raises(TypeError):
        _ = pending + 1  # pyright: ignore[reportOperatorIssue]
    with pytest.raises(AttributeError):
        pending.set_alias("rn")  # pyright: ignore[reportAttributeAccessIssue]
    with pytest.raises(AttributeError):
        i.price.lag().sum()  # pyright: ignore[reportAttributeAccessIssue]

    aliased = i.price.sum().set_alias("total")
    assert not hasattr(aliased, "over")


def test_is_in_parses_null(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values(id_1=1, name="bolt", price=0.5).run()
    InsertBuilder(t).from_values(id_1=2, name="nut", price=None).run()
    InsertBuilder(t).from_values(id_1=3, name="gear", price=9.0).run()

    builder = SelectBuilder(t.name, from_=t).where(t.price.is_in([0.5, None]))
    rendered = builder.render()
    assert "IS NULL" in rendered and "OR" in rendered

    _, df = builder.run()
    assert sorted(df["name"].tolist()) == ["bolt", "nut"]


def test_not_in_parses_null(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values(id_1=1, name="bolt", price=0.5).run()
    InsertBuilder(t).from_values(id_1=2, name="nut", price=None).run()
    InsertBuilder(t).from_values(id_1=3, name="gear", price=9.0).run()

    _, df = SelectBuilder(t.name, from_=t).where(t.price.not_in([0.5, None])).run()
    assert df["name"].tolist() == ["gear"]

    _, raw = SelectBuilder(t.name, from_=t).where(t.price.not_in([0.5, None], parse_null=False)).run()
    assert raw["name"].tolist() == []


def test_is_in_with_only_null(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values(id_1=1, name="bolt", price=0.5).run()
    InsertBuilder(t).from_values(id_1=2, name="nut", price=None).run()

    builder = SelectBuilder(t.name, from_=t).where(t.price.is_in([None]))
    rendered = builder.render()
    assert "IS NULL" in rendered and "IN" not in rendered.replace("IS NULL", "")

    _, df = builder.run()
    assert df["name"].tolist() == ["nut"]


def test_is_in_raw_null(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values(id_1=1, name="bolt", price=0.5).run()
    InsertBuilder(t).from_values(id_1=2, name="nut", price=None).run()

    builder = SelectBuilder(t.name, from_=t).where(t.price.is_in([0.5, None], parse_null=False))
    assert "IS NULL" not in builder.render()

    _, df = builder.run()
    assert df["name"].tolist() == ["bolt"]


def test_deferred_parameter_override(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values(id_1=1, name="cheap", price=1.0).run()
    InsertBuilder(t).from_values(id_1=2, name="dear", price=9.0).run()

    builder = SelectBuilder(t.name, from_=t).where(t.price > 1)
    _, df = builder.run(price_1=8)
    assert df["name"].tolist() == ["dear"]


def test_scalar_subquery_renders_top_on_mssql():
    m = MSSQL_HANDLER.get_unit(mssql_items)
    sub = MSSQL_HANDLER.get_unit(mssql_items).set_alias("sub")
    latest = (
        SelectBuilder(sub.id_1, from_=sub)
        .order_by(sub.id_1.desc())
        .limit(1)
        .as_scalar()
        .set_alias("latest")
    )
    rendered = SelectBuilder(m.id_1, latest, from_=m).render()
    assert "TOP 1" in rendered
    assert "latest" in rendered


def test_scalar_subquery_renders_limit_on_sqlite():
    i = SQLITE_HANDLER.get_unit(items)
    sub = SQLITE_HANDLER.get_unit(items).set_alias("sub")
    latest = SelectBuilder(sub.id_1, from_=sub).order_by(sub.id_1.desc()).limit(1).as_scalar()
    rendered = SelectBuilder(i.name, latest, from_=i).render()
    assert "LIMIT" in rendered
    assert "TOP" not in rendered


def test_scalar_subquery_correlates_on_outer_column():
    i = SQLITE_HANDLER.get_unit(items)
    p = SQLITE_HANDLER.get_unit(parts)
    label = (
        SelectBuilder(p.label, from_=p).where(p.id_1 == i.id_1).limit(1).as_scalar().set_alias("label")
    )
    rendered = SelectBuilder(i.name, label, from_=i).render()
    assert rendered.count("FROM main.items") == 1
    assert "FROM main.parts" in rendered


def test_scalar_subquery_runs(handler: EngineHandler):
    items_tmp = TempBuilder(handler.get_unit(items))
    items_tmp.run()
    parts_tmp = TempBuilder(handler.get_unit(parts))
    parts_tmp.run()

    t, p = items_tmp.unit(), parts_tmp.unit()
    InsertBuilder(t).from_values(id_1=1, name="bolt", price=0.5).run()
    InsertBuilder(t).from_values(id_1=2, name="nut", price=1.5).run()
    InsertBuilder(p).from_values(id_1=1, label="washer").run()
    InsertBuilder(p).from_values(id_1=2, label="gear").run()

    label = (
        SelectBuilder(p.label, from_=p).where(p.id_1 == t.id_1).limit(1).as_scalar().set_alias("label")
    )
    _, df = SelectBuilder(t.name, label, from_=t).order_by(t.id_1).run()
    assert df["label"].tolist() == ["washer", "gear"]


def test_from_subquery_join_renders_derived_table():
    i = SQLITE_HANDLER.get_unit(items)
    p = SQLITE_HANDLER.get_unit(parts)
    active = SelectBuilder(p, from_=p).where(p.id_1 > 1).as_object("p")
    rendered = SelectBuilder(i.name, active.label, from_=i).join(
        "INNER", active, i.id_1 == active.id_1
    ).render()
    assert "JOIN (SELECT" in rendered
    assert ") AS p" in rendered
    assert "WHERE" in rendered


def test_from_subquery_join_runs(handler: EngineHandler):
    items_tmp = TempBuilder(handler.get_unit(items))
    items_tmp.run()
    parts_tmp = TempBuilder(handler.get_unit(parts))
    parts_tmp.run()

    t, p = items_tmp.unit(), parts_tmp.unit()
    InsertBuilder(t).from_values(id_1=1, name="bolt", price=0.5).run()
    InsertBuilder(t).from_values(id_1=2, name="nut", price=1.5).run()
    InsertBuilder(p).from_values(id_1=1, label="washer").run()
    InsertBuilder(p).from_values(id_1=2, label="gear").run()

    active = SelectBuilder(p, from_=p).where(p.id_1 > 1).as_object("p")
    _, df = (
        SelectBuilder(t.name, active.label, from_=t)
        .join("INNER", active, t.id_1 == active.id_1)
        .run()
    )
    assert df["name"].tolist() == ["nut"]
    assert df["label"].tolist() == ["gear"]


def test_paginate_compiles_limit_and_offset():
    i = SQLITE_HANDLER.get_unit(items)
    sql = SelectBuilder(i.name, from_=i).order_by(i.id_1).paginate(3, 20).to_sql()

    assert sql.raw_query is not None
    assert "LIMIT" in sql.raw_query
    assert "OFFSET" in sql.raw_query

    params = sql.query_parameters
    assert isinstance(params, dict)
    assert 20 in params.values()
    assert 40 in params.values()


def test_paginate_runs(handler: EngineHandler):
    items_tmp = TempBuilder(handler.get_unit(items))
    items_tmp.run()

    t = items_tmp.unit()
    for id_1, name in enumerate(["a", "b", "c", "d", "e"], start=1):
        InsertBuilder(t).from_values(id_1=id_1, name=name, price=float(id_1)).run()

    def page(number: int) -> list[str]:
        _, df = SelectBuilder(t.name, from_=t).order_by(t.id_1).paginate(number, 2).run()
        return df["name"].tolist()

    assert page(1) == ["a", "b"]
    assert page(2) == ["c", "d"]
    assert page(3) == ["e"]
