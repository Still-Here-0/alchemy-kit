from typing import Any, cast

import numpy as np
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


def _parameters(insert: InsertBuilder) -> dict[str, Any]:
    return cast(dict[str, Any], insert.to_sqls()[0].query_parameters)


def test_insert_binds_missing_dataframe_values_as_null():
    df = pd.DataFrame({
        "id_1": [1, 2],
        "name": ["bolt", None],
        "price": [0.5, np.nan],
    })

    parameters = _parameters(InsertBuilder(SQLITE_HANDLER.get_unit(items)).from_dataframe(df))

    assert parameters["name_m1"] is None
    assert parameters["price_m1"] is None
    assert parameters["name_m0"] == "bolt"


def test_insert_stores_missing_dataframe_values_as_null(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()

    count, _ = InsertBuilder(tmp.unit()).from_dataframe(pd.DataFrame({
        "id_1": [1, 2],
        "name": ["bolt", "nut"],
        "price": [0.5, np.nan],
    })).run()
    assert count == 2

    _, stored = SelectBuilder(tmp.unit().price, from_=tmp.unit()).run()
    assert stored["price"].isna().sum() == 1


@pytest.mark.parametrize("missing", [np.nan, pd.NA, pd.NaT, None])
def test_insert_binds_every_pandas_missing_marker_as_null(missing: object):
    df = pd.DataFrame({"id_1": [1], "name": ["bolt"], "price": [missing]})

    parameters = _parameters(InsertBuilder(SQLITE_HANDLER.get_unit(items)).from_dataframe(df))

    assert parameters["price_m0"] is None


def test_insert_keeps_non_scalar_dataframe_values():
    df = pd.DataFrame({"id_1": [1], "name": [["a", "b"]], "price": [0.5]})

    parameters = _parameters(InsertBuilder(SQLITE_HANDLER.get_unit(items)).from_dataframe(df))

    assert parameters["name_m0"] == ["a", "b"]


def test_insert_rejects_aliased_unit():
    with pytest.raises(TypeError):
        InsertBuilder(SQLITE_HANDLER.get_unit(items).set_alias("x"))
