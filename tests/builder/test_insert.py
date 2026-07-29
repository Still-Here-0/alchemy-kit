import warnings
from typing import Any, cast

import numpy as np
import pandas as pd
import pytest

from alchemy_kit.builder import InsertBuilder, SelectBuilder, TempBuilder
from alchemy_kit.connect._engine_handler import EngineHandler
from alchemy_kit.resources.dialect_map.mssql import MssqlMap
from alchemy_kit.types.errors import StatementLimitError
from alchemy_kit.types.statement_limits import StatementLimits

from _helpers import (
    MSSQL_HANDLER,
    ORACLE_HANDLER,
    SQLITE_HANDLER,
    items,
    mssql_items,
    mssql_wide,
    oracle_items,
)


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


def _records(insert: InsertBuilder) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], insert.to_sql().query_parameters)


def test_insert_binds_missing_dataframe_values_as_null():
    df = pd.DataFrame({
        "id_1": [1, 2],
        "name": ["bolt", None],
        "price": [0.5, np.nan],
    })

    records = _records(InsertBuilder(SQLITE_HANDLER.get_unit(items)).from_dataframe(df))

    assert records[1]["name"] is None
    assert records[1]["price"] is None
    assert records[0]["name"] == "bolt"


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

    records = _records(InsertBuilder(SQLITE_HANDLER.get_unit(items)).from_dataframe(df))

    assert records[0]["price"] is None


def test_insert_keeps_non_scalar_dataframe_values():
    df = pd.DataFrame({"id_1": [1], "name": [["a", "b"]], "price": [0.5]})

    records = _records(InsertBuilder(SQLITE_HANDLER.get_unit(items)).from_dataframe(df))

    assert records[0]["name"] == ["a", "b"]


@pytest.mark.parametrize(
    ("handler_", "model", "expected_query", "id_name"),
    [
        (
            ORACLE_HANDLER, oracle_items,
            'INSERT INTO "APP"."ITEMS" ("ID") VALUES (:ID)', "ID",
        ),
        (
            MSSQL_HANDLER, mssql_items,
            "INSERT INTO dbo.items (id) VALUES (:id)", "id",
        ),
        (
            SQLITE_HANDLER, items,
            "INSERT INTO main.items (id) VALUES (:id)", "id",
        ),
    ],
)
def test_insert_binds_one_record_per_row_on_every_dialect(
    handler_: EngineHandler,
    model: Any,
    expected_query: str,
    id_name: str,
):
    df = pd.DataFrame({"id_1": [1, 2, 3]})

    sql = InsertBuilder(handler_.get_unit(model)).from_dataframe(df).to_sql()

    assert sql.raw_query == expected_query
    assert sql.query_parameters == [{id_name: 1}, {id_name: 2}, {id_name: 3}]


def test_insert_binds_a_single_row_as_a_one_record_list():
    df = pd.DataFrame({"id_1": [1], "name": ["bolt"]})

    sql = InsertBuilder(ORACLE_HANDLER.get_unit(oracle_items)).from_dataframe(df).to_sql()

    assert sql.raw_query == 'INSERT INTO "APP"."ITEMS" ("ID", "NAME") VALUES (:ID, :NAME)'
    assert sql.query_parameters == [{"ID": 1, "NAME": "bolt"}]


def test_insert_compiles_one_statement_however_many_rows():
    df = pd.DataFrame({"id_1": range(100_000), "name": ["bolt"] * 100_000})

    sql = InsertBuilder(ORACLE_HANDLER.get_unit(oracle_items)).from_dataframe(df).to_sql()

    assert sql.raw_query == 'INSERT INTO "APP"."ITEMS" ("ID", "NAME") VALUES (:ID, :NAME)'
    assert len(sql.query_parameters) == 100_000


def test_insert_far_past_the_mssql_parameter_limit_binds_one_row_of_names():
    df = pd.DataFrame({
        "id_1": range(2000),
        "name": ["bolt"] * 2000,
        "price": [0.5] * 2000,
    })

    sql = InsertBuilder(MSSQL_HANDLER.get_unit(mssql_wide)).from_dataframe(df).to_sql()

    assert len(sql.query_parameters) == 2000
    assert sql.parameter_names() == ["id", "name", "price"]


def test_insert_row_wider_than_the_parameter_budget_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(MssqlMap, "limits", StatementLimits(max_params=2))
    df = pd.DataFrame({"id_1": range(10), "name": ["bolt"] * 10, "price": [0.5] * 10})

    insert = InsertBuilder(MSSQL_HANDLER.get_unit(mssql_wide)).from_dataframe(df)

    with pytest.raises(StatementLimitError) as error:
        insert.to_sql()

    assert error.value.needed == 3
    assert error.value.budget == 2
    assert "write fewer columns at a time" in str(error.value)
    assert "TempBuilder" not in str(error.value)


def test_insert_rejects_rows_that_set_different_columns():
    unit = SQLITE_HANDLER.get_unit(items)
    insert = (
        InsertBuilder(unit)
        .from_dataframe(pd.DataFrame({"id_1": [1], "name": ["bolt"], "price": [0.5]}))
        .from_dataframe(pd.DataFrame({"id_1": [2], "name": ["nut"]})) # type: ignore
    )

    with pytest.raises(ValueError) as error:
        insert.to_sql()

    assert "same columns" in str(error.value)


def test_insert_rejects_a_row_value_that_is_a_sql_expression():
    unit = SQLITE_HANDLER.get_unit(items)
    df = pd.DataFrame({"id_1": [1], "name": ["bolt"], "price": [unit.price + 1]})

    with pytest.raises(TypeError) as error:
        InsertBuilder(unit).from_dataframe(df).to_sql()

    assert "'price'" in str(error.value)


def test_insert_of_an_empty_dataframe_is_a_no_op(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()

    empty = pd.DataFrame({"id_1": [], "name": [], "price": []})
    count, data = InsertBuilder(tmp.unit()).from_dataframe(empty).run()

    assert count == 0
    assert data.empty

    _, stored = SelectBuilder(tmp.unit().id_1, from_=tmp.unit()).run()
    assert stored.empty


def test_insert_round_trips_far_more_rows_than_any_parameter_limit(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()

    insert = InsertBuilder(tmp.unit()).from_dataframe(pd.DataFrame({
        "id_1": range(50_000),
        "name": ["bolt"] * 50_000,
        "price": [0.5] * 50_000,
    }))

    sql = insert.to_sql()
    assert isinstance(sql.query_parameters, list)
    assert len(sql.parameter_names()) == 3

    count, _ = insert.run()
    assert count == 50_000

    _, stored = SelectBuilder(tmp.unit().id_1, from_=tmp.unit()).run()
    assert len(stored) == 50_000


def test_insert_renders_the_template_it_binds_records_to():
    df = pd.DataFrame({"id_1": [1, 2], "name": ["bolt", "nut"]})

    rendered = InsertBuilder(ORACLE_HANDLER.get_unit(oracle_items)).from_dataframe(df).render()

    assert rendered == 'INSERT INTO "APP"."ITEMS" ("ID", "NAME") VALUES (:ID, :NAME)'


def test_from_values_still_compiles_through_sqlalchemy():
    unit = ORACLE_HANDLER.get_unit(oracle_items)

    sql = InsertBuilder(unit).from_values((unit.id_1, 7), (unit.name, "bolt")).to_sql()

    assert sql.raw_query == 'INSERT INTO "APP"."ITEMS" ("ID", "NAME") VALUES (:ID, :NAME)'
    assert sql.query_parameters == {"ID": 7, "NAME": "bolt"}


def test_insert_rejects_aliased_unit():
    with pytest.raises(TypeError):
        InsertBuilder(SQLITE_HANDLER.get_unit(items).set_alias("x"))


def test_to_sqls_inlines_each_chunk_as_a_multi_row_values_clause(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    insert = InsertBuilder(tmp.unit()).from_dataframe(pd.DataFrame([
        {"id_1": 1, "name": "bolt", "price": 0.5},
        {"id_1": 2, "name": "nut", "price": 1.5},
        {"id_1": 3, "name": "gear", "price": 9.0},
    ]))

    insert_sqls = insert.to_sqls(chunk_size=2)

    assert [len(sql.query_parameters) for sql in insert_sqls] == [6, 3]
    assert str(insert_sqls[0].raw_query).count("(:id_m") == 2
    assert str(insert_sqls[1].raw_query).count("(:id_m") == 1

    results = handler.run_sqls([
        tmp.to_sql(),
        *insert_sqls,
        SelectBuilder(tmp.unit().name, from_=tmp.unit()).to_sql(),
    ])

    assert sorted(results[-1][1]["name"].tolist()) == ["bolt", "gear", "nut"]


def test_to_sqls_without_a_chunk_size_splits_on_the_dialect_row_cap():
    df = pd.DataFrame({"id_1": range(2500)})

    sqls = InsertBuilder(MSSQL_HANDLER.get_unit(mssql_items)).from_dataframe(df).to_sqls()

    assert [len(sql.query_parameters) for sql in sqls] == [1000, 1000, 500]


def test_to_sqls_splits_on_the_parameter_budget_when_it_binds_first():
    df = pd.DataFrame({
        "id_1": range(1500),
        "name": ["bolt"] * 1500,
        "price": [0.5] * 1500,
    })

    sqls = InsertBuilder(MSSQL_HANDLER.get_unit(mssql_wide)).from_dataframe(df).to_sqls()

    rows_per_statement = MssqlMap.limits.param_budget // 3
    assert rows_per_statement < 1000
    assert [len(sql.query_parameters) for sql in sqls] == [
        rows_per_statement * 3,
        rows_per_statement * 3,
        (1500 - 2 * rows_per_statement) * 3,
    ]
    assert all(len(sql.query_parameters) <= MssqlMap.limits.param_budget for sql in sqls)


def test_to_sqls_narrows_a_chunk_size_the_dialect_cannot_carry():
    df = pd.DataFrame({"id_1": range(2000)})

    sqls = InsertBuilder(MSSQL_HANDLER.get_unit(mssql_items)).from_dataframe(df).to_sqls(chunk_size=1500)

    assert [len(sql.query_parameters) for sql in sqls] == [1000, 1000]


def test_to_sqls_on_a_dialect_without_multi_row_values_raises():
    df = pd.DataFrame({"id_1": [1, 2], "name": ["bolt", "nut"]})

    insert = InsertBuilder(ORACLE_HANDLER.get_unit(oracle_items)).from_dataframe(df)

    with pytest.raises(ValueError) as error:
        insert.to_sqls()

    assert "one VALUES clause" in str(error.value)
    assert "use to_sql" in str(error.value)


def test_to_sqls_rejects_a_chunk_size_below_one():
    df = pd.DataFrame({"id_1": [1], "name": ["bolt"], "price": [0.5]})

    insert = InsertBuilder(SQLITE_HANDLER.get_unit(items)).from_dataframe(df)

    with pytest.raises(ValueError) as error:
        insert.to_sqls(chunk_size=0)

    assert "chunk_size must be at least 1" in str(error.value)


def test_to_sqls_of_a_row_wider_than_the_budget_still_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(MssqlMap, "limits", StatementLimits(max_params=2))
    df = pd.DataFrame({"id_1": range(10), "name": ["bolt"] * 10, "price": [0.5] * 10})

    insert = InsertBuilder(MSSQL_HANDLER.get_unit(mssql_wide)).from_dataframe(df)

    with pytest.raises(StatementLimitError):
        insert.to_sqls()


def test_to_sqls_of_a_source_without_multiple_rows_returns_the_single_statement():
    unit = ORACLE_HANDLER.get_unit(oracle_items)
    empty = pd.DataFrame({"id_1": [], "name": []})

    values_sqls = InsertBuilder(unit).from_values((unit.id_1, 7), (unit.name, "bolt")).to_sqls()
    empty_sqls = InsertBuilder(unit).from_dataframe(empty).to_sqls()

    assert [sql.query_parameters for sql in values_sqls] == [{"ID": 7, "NAME": "bolt"}]
    assert [sql.query_parameters for sql in empty_sqls] == [[]]


def test_chunked_run_aggregates_counts_without_warning(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    insert = InsertBuilder(tmp.unit()).from_dataframe(pd.DataFrame([
        {"id_1": 1, "name": "bolt", "price": 0.5},
        {"id_1": 2, "name": "nut", "price": 1.5},
        {"id_1": 3, "name": "gear", "price": 9.0},
    ]))

    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        count, data = insert.run(chunk_size=2)

    assert count == 3
    assert data.empty
    assert not [w for w in recorded if issubclass(w.category, DeprecationWarning)]

    _, stored = SelectBuilder(tmp.unit().name, from_=tmp.unit()).run()
    assert sorted(stored["name"].tolist()) == ["bolt", "gear", "nut"]


def test_run_without_a_chunk_size_does_not_warn(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    insert = InsertBuilder(tmp.unit()).from_dataframe(
        pd.DataFrame({"id_1": [1], "name": ["bolt"], "price": [0.5]})
    )

    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        count, _ = insert.run()

    assert count == 1
    assert not [w for w in recorded if issubclass(w.category, DeprecationWarning)]
