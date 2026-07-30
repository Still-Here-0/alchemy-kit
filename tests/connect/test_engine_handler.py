from decimal import Decimal
from typing import Any, cast

import pandas as pd
import pytest
import sqlalchemy

from alchemy_kit.connect._engine_handler import EngineHandler
from alchemy_kit.resources._sql import SQL


@pytest.fixture
def handler():
    engine = sqlalchemy.create_engine("sqlite://")
    return EngineHandler(engine, cast(Any, None))


def test_run_sqls_shares_one_connection(handler: EngineHandler):
    results = handler.run_sqls([
        SQL(raw_query="CREATE TEMPORARY TABLE scratch (id INTEGER)"),
        SQL(raw_query="INSERT INTO scratch VALUES (1), (2)"),
        SQL(raw_query="SELECT id FROM scratch ORDER BY id"),
    ])

    assert len(results) == 3
    assert results[1][0] == 2
    assert results[2][1]["id"].tolist() == [1, 2]


def test_run_sqls_rolls_back_all_on_failed_check(handler: EngineHandler):
    handler.run_sql(SQL(raw_query="CREATE TABLE t (id INTEGER)"))

    results = handler.run_sqls([
        SQL(raw_query="INSERT INTO t VALUES (1)"),
        SQL(raw_query="INSERT INTO t VALUES (2)", f_check=lambda _: False),
        SQL(raw_query="INSERT INTO t VALUES (3)"),
    ])

    assert len(results) == 2
    assert all(count is None and df.empty for count, df in results)

    _, df = handler.run_sql(SQL(raw_query="SELECT count(*) AS n FROM t"))
    assert df["n"].iloc[0] == 0


def test_insert_data_appends_and_commits(handler: EngineHandler):
    handler.run_sql(SQL(raw_query="CREATE TABLE items (id INTEGER, name VARCHAR)"))

    inserted = handler.insert_data(
        pd.DataFrame({"id": [1, 2], "name": ["a", "b"]}), "main", "items", "main"
    )
    assert inserted == 2

    _, df = handler.run_sql(SQL(raw_query="SELECT * FROM items ORDER BY id"))
    assert df["name"].tolist() == ["a", "b"]


def test_record_parameters_are_typed_like_a_single_mapping(handler: EngineHandler):
    counts = handler.run_sqls([
        SQL(raw_query="CREATE TEMPORARY TABLE priced (label TEXT, amount NUMERIC)"),
        SQL(
            raw_query="INSERT INTO priced (label, amount) VALUES (:label, :amount)",
            query_parameters=[
                {"label": "a", "amount": Decimal("1.50")},
                {"label": "b", "amount": Decimal("2.25")},
            ],
        ),
        SQL(raw_query="SELECT sum(amount) AS total FROM priced"),
    ])

    assert counts[1][0] == 2
    assert counts[-1][1]["total"].tolist() == [3.75]


def test_records_are_typed_from_the_first_one_holding_a_value(handler: EngineHandler):
    counts = handler.run_sqls([
        SQL(raw_query="CREATE TEMPORARY TABLE priced (label TEXT, amount NUMERIC)"),
        SQL(
            raw_query="INSERT INTO priced (label, amount) VALUES (:label, :amount)",
            query_parameters=[
                {"label": "a", "amount": None},
                {"label": "b", "amount": Decimal("2.25")},
            ],
        ),
        SQL(raw_query="SELECT count(amount) AS filled FROM priced"),
    ])

    assert counts[1][0] == 2
    assert counts[-1][1]["filled"].tolist() == [1]


def test_an_empty_record_list_executes_zero_times(handler: EngineHandler):
    counts = handler.run_sqls([
        SQL(raw_query="CREATE TEMPORARY TABLE priced (label TEXT, amount NUMERIC)"),
        SQL(
            raw_query="INSERT INTO priced (label, amount) VALUES (:label, :amount)",
            query_parameters=[],
        ),
        SQL(raw_query="SELECT count(*) AS stored FROM priced"),
    ])

    assert counts[1][0] == 0
    assert counts[1][1].empty
    assert counts[-1][1]["stored"].tolist() == [0]


def test_run_sql_reports_an_empty_record_list_as_no_rows(handler: EngineHandler):
    handler.run_sql(SQL(raw_query="CREATE TABLE priced (label TEXT)"))

    count, data = handler.run_sql(
        SQL(raw_query="INSERT INTO priced (label) VALUES (:label)", query_parameters=[])
    )

    assert count == 0
    assert data.empty


def test_records_carrying_a_collection_bind_as_column_data(handler: EngineHandler):
    counts = handler.run_sqls([
        SQL(raw_query="CREATE TEMPORARY TABLE tagged (label TEXT, tags TEXT)"),
        SQL(
            raw_query="INSERT INTO tagged (label, tags) VALUES (:label, :tags)",
            query_parameters=[
                {"label": "a", "tags": "['x', 'y']"},
                {"label": "b", "tags": "[]"},
            ],
        ),
        SQL(raw_query="SELECT tags FROM tagged ORDER BY label"),
    ])

    assert counts[1][0] == 2
    assert counts[-1][1]["tags"].tolist() == ["['x', 'y']", "[]"]


def test_a_mapping_statement_still_expands_a_collection_into_an_in_clause(handler: EngineHandler):
    select = "SELECT label FROM tagged WHERE label IN :wanted ORDER BY label"
    counts = handler.run_sqls([
        SQL(raw_query="CREATE TEMPORARY TABLE tagged (label TEXT)"),
        SQL(
            raw_query="INSERT INTO tagged (label) VALUES (:label)",
            query_parameters=[{"label": "a"}, {"label": "b"}, {"label": "c"}],
        ),
        SQL(raw_query=select, query_parameters={"wanted": ("a", "c")}),
        SQL(raw_query=select, query_parameters={"wanted": frozenset({"a", "b"})}),
    ])

    assert counts[-2][1]["label"].tolist() == ["a", "c"]
    assert counts[-1][1]["label"].tolist() == ["a", "b"]
