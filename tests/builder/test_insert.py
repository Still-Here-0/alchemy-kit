import pandas as pd
import pytest

from alchemy_kit.builder import InsertBuilder, SelectBuilder, TempBuilder
from alchemy_kit.connect._engine_handler import EngineHandler

from _helpers import SQLITE_HANDLER, items


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
