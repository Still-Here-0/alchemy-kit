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
