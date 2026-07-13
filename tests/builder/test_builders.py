from typing import Any, Optional, cast

import pandera.pandas as pa
import pytest
import sqlalchemy
from pandera.typing import Series

from alchemy_kit.builder import InsertBuilder, SelectBuilder, TempBuilder
from alchemy_kit.connect._engine_handler import EngineHandler
from alchemy_kit.model.base_model import BaseModel, MetaData
from alchemy_kit.resources._sql import SQL
from alchemy_kit.resources.dialect_map import get_sa_dialect
from alchemy_kit.resources.dialect_map.mssql import MssqlMap
from alchemy_kit.resources.dialect_map.sqlite import SqliteMap
from alchemy_kit.types.dialect_types import DialectTypes
from alchemy_kit.types.sql_type_parameters import MssqlTypeParameters, SqliteTypeParameters


class items(BaseModel[SqliteTypeParameters]):
    _dialect = DialectTypes.SQLITE
    _map = SqliteMap

    id_1: Series[int] = pa.Field(nullable=False, alias="id", metadata={"original_type": "integer"})
    name: Series[str] = pa.Field(nullable=False, alias="name", metadata={"original_type": "varchar"})
    price: Optional[Series[float]] = pa.Field(nullable=True, alias="price", metadata={"original_type": "real"})

    class Config(BaseModel.Config):
        metadata = MetaData(
            schema_name="main", obj_name="items", obj_type="Table",
            reference_name='"main"."items"', description=None,
        )


class parts(BaseModel[SqliteTypeParameters]):
    _dialect = DialectTypes.SQLITE
    _map = SqliteMap

    id_1: Series[int] = pa.Field(nullable=False, alias="id", metadata={"original_type": "integer"})
    label: Series[str] = pa.Field(nullable=False, alias="label", metadata={"original_type": "varchar"})

    class Config(BaseModel.Config):
        metadata = MetaData(
            schema_name="main", obj_name="parts", obj_type="Table",
            reference_name='"main"."parts"', description=None,
        )


class mssql_items(BaseModel[MssqlTypeParameters]):
    _dialect = DialectTypes.MSSQL
    _map = MssqlMap

    id_1: Series[int] = pa.Field(nullable=False, alias="id", metadata={"original_type": "int"})

    class Config(BaseModel.Config):
        metadata = MetaData(
            schema_name="dbo", obj_name="items", obj_type="Table",
            reference_name="[dbo].[items]", description=None,
        )


@pytest.fixture
def handler():
    engine = sqlalchemy.create_engine("sqlite://")
    return EngineHandler(engine, cast(Any, None))


def test_every_dialect_compiles_with_named_paramstyle():
    for dialect in DialectTypes:
        assert get_sa_dialect(dialect).paramstyle == "named"


def test_select_render_and_parameters():
    i = items.get_unit()
    builder = (
        SelectBuilder(i.name, i.price.sum().set_alias("total"))
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
    i = items.get_unit()
    base = SelectBuilder(i.name)
    filtered = base.where(i.price > 1)

    assert "WHERE" not in base.render()
    assert "WHERE" in filtered.render()


def test_cross_join_compiles_and_runs(handler: EngineHandler):
    tmp = TempBuilder(items.get_unit())
    tmp.run(handler)
    t = tmp.unit()
    InsertBuilder(t).values(id_1=1, name="bolt", price=0.5).run(handler)
    InsertBuilder(t).values(id_1=2, name="nut", price=1.5).run(handler)

    o = tmp.unit().set_alias("o")
    builder = SelectBuilder(t.name, o.price).join("CROSS", o)
    assert "ON 1 = 1" in builder.render()

    _, df = builder.run(handler)
    assert len(df) == 4


def test_right_join_keeps_unmatched_right_rows(handler: EngineHandler):
    items_tmp = TempBuilder(items.get_unit())
    items_tmp.run(handler)
    parts_tmp = TempBuilder(parts.get_unit())
    parts_tmp.run(handler)

    t, p = items_tmp.unit(), parts_tmp.unit()
    InsertBuilder(t).values(id_1=1, name="bolt", price=0.5).run(handler)
    InsertBuilder(p).values(id_1=1, label="washer").run(handler)
    InsertBuilder(p).values(id_1=2, label="nut").run(handler)

    builder = SelectBuilder(t.name, p.id_1).join("RIGHT", p, t.id_1 == p.id_1)
    assert "LEFT OUTER JOIN" in builder.render()

    _, df = builder.run(handler)
    assert sorted(df["id"].tolist()) == [1, 2]
    assert df["name"].isna().sum() == 1


def test_joins_chain_after_right(handler: EngineHandler):
    items_tmp = TempBuilder(items.get_unit())
    items_tmp.run(handler)
    parts_tmp = TempBuilder(parts.get_unit())
    parts_tmp.run(handler)

    t, p = items_tmp.unit(), parts_tmp.unit()
    InsertBuilder(t).values(id_1=1, name="bolt", price=0.5).run(handler)
    InsertBuilder(p).values(id_1=1, label="washer").run(handler)
    InsertBuilder(p).values(id_1=2, label="nut").run(handler)

    third = parts_tmp.unit().set_alias("third")
    builder = (
        SelectBuilder(t.name, p.id_1)
        .join("RIGHT", p, t.id_1 == p.id_1)
        .join("INNER", third, p.id_1 == third.id_1)
    )
    rendered = builder.render()
    assert rendered.count("JOIN") == 2

    _, df = builder.run(handler)
    assert sorted(df["id"].tolist()) == [1, 2]


def test_join_condition_arity():
    i = items.get_unit()
    o = items.get_unit().set_alias("o")
    with pytest.raises(TypeError):
        SelectBuilder(i.name).join("CROSS", o, i.id_1 == o.id_1)
    with pytest.raises(TypeError):
        SelectBuilder(i.name).join("INNER", o)


def test_insert_rejects_aliased_unit():
    with pytest.raises(TypeError):
        InsertBuilder(items.get_unit().set_alias("x"))


def test_temp_round_trip_through_run_sql(handler: EngineHandler):
    tmp = TempBuilder(items.get_unit())
    assert 'CREATE TEMPORARY TABLE "TEMP_items"' in tmp.render()
    tmp.run(handler)

    t = tmp.unit()
    for row in [
        dict(id_1=1, name="bolt", price=0.5),
        dict(id_1=2, name="nut", price=1.5),
        dict(id_1=3, name="gear", price=9.0),
    ]:
        InsertBuilder(t).values(**row).run(handler)

    _, df = SelectBuilder(t.name, t.price).where(t.price > 1).order_by(t.price.desc()).run(handler)
    assert df["name"].tolist() == ["gear", "nut"]

    handler.run_sql(SQL(raw_query="CREATE TABLE main.items (id INTEGER NOT NULL, name VARCHAR NOT NULL, price REAL)"))
    moved, _ = (
        InsertBuilder(items.get_unit())
        .from_select(SelectBuilder(t.id_1, t.name, t.price).where(t.price > 1))
        .run(handler)
    )
    assert moved == 2

    _, real = SelectBuilder(items.get_unit()).run(handler)
    assert sorted(real["name"].tolist()) == ["gear", "nut"]


def test_global_temp_rejected_on_unsupported_dialect():
    with pytest.raises(ValueError):
        TempBuilder(items.get_unit(), global_temp=True)


def test_mssql_temp_naming():
    assert "[#TEMP_items]" in TempBuilder(mssql_items.get_unit()).render()
    assert "[##TEMP_items]" in TempBuilder(mssql_items.get_unit(), global_temp=True).render()


def test_deferred_parameter_override(handler: EngineHandler):
    tmp = TempBuilder(items.get_unit())
    tmp.run(handler)
    t = tmp.unit()
    InsertBuilder(t).values(id_1=1, name="cheap", price=1.0).run(handler)
    InsertBuilder(t).values(id_1=2, name="dear", price=9.0).run(handler)

    builder = SelectBuilder(t.name).where(t.price > 1)
    _, df = builder.run(handler, price_1=8)
    assert df["name"].tolist() == ["dear"]
