import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pandas as pd
import pytest
import sqlalchemy

from alchemy_kit.connect._engine_handler import EngineHandler
from alchemy_kit.connect._info import ConnectionInfo
from alchemy_kit.model._model_def import MetadataExtractor
from alchemy_kit.model._schema_config import SchemaConfig
from alchemy_kit.model._utils import parse_db
from alchemy_kit.resources._better_logger import BetterLogger
from alchemy_kit.resources.dialect_map import DIALECT_MAPS, DialectMap, MssqlMap, OracleMap

LOGGER = BetterLogger(logging.getLogger("test_inspector_def"))


@pytest.fixture
def sqlite_info(tmp_path: Path) -> ConnectionInfo:
    db_path = tmp_path / "fixture.db"

    engine = sqlalchemy.create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.exec_driver_sql("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                email VARCHAR(120) NOT NULL,
                age INTEGER CHECK (age >= 18),
                country CHAR(2) DEFAULT 'PT',
                code VARCHAR(8),
                UNIQUE (email)
            )
        """)
        conn.exec_driver_sql("CREATE UNIQUE INDEX ux_users_code ON users (code) WHERE code IS NOT NULL")
        conn.exec_driver_sql("""
            CREATE TABLE orders (
                id INTEGER,
                seq INTEGER,
                user_id INTEGER NOT NULL,
                total NUMERIC(10, 2) CHECK (total > 0),
                start_date DATE,
                end_date DATE,
                PRIMARY KEY (id, seq),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                CHECK (start_date <= end_date)
            )
        """)
        conn.exec_driver_sql("CREATE UNIQUE INDEX ux_orders_user_seq ON orders (user_id, seq)")
        conn.exec_driver_sql("CREATE VIEW v_users AS SELECT id, email FROM users")
    engine.dispose()

    return ConnectionInfo(sqlalchemy.URL.create("sqlite", database=str(db_path)), "inspector-test")


def test_parse_db_via_inspector(sqlite_info: ConnectionInfo):
    model = parse_db(sqlite_info, SchemaConfig(), LOGGER)

    assert list(model.schemas) == ["main"]
    objects = model.schemas["main"].objects
    assert {name: obj.type for name, obj in objects.items()} == {
        "users": "Table",
        "orders": "Table",
        "v_users": "View",
    }


def test_parse_db_columns(sqlite_info: ConnectionInfo):
    model = parse_db(sqlite_info, SchemaConfig(), LOGGER)
    users = model.schemas["main"].objects["users"]

    assert users.columns["id"].is_primary_key
    assert users.columns["email"].is_unique
    assert users.columns["email"].type == "varchar"
    assert users.columns["email"].max_length == 120
    assert not users.columns["email"].is_nullable
    assert users.columns["age"].is_nullable
    assert users.columns["country"].has_default
    assert users.columns["country"].default == "'PT'"

    assert users.columns["id"].is_unique

    orders = model.schemas["main"].objects["orders"]
    assert orders.columns["id"].is_primary_key
    assert orders.columns["seq"].is_primary_key
    assert not orders.columns["id"].is_unique
    assert not orders.columns["seq"].is_unique
    assert orders.columns["total"].precision == 10
    assert orders.columns["total"].scale == 2

    fk_ref = orders.columns["user_id"].fk_ref
    assert fk_ref is not None
    assert (fk_ref.schema, fk_ref.table, fk_ref.column) == ("main", "users", "id")


def test_parse_db_constraints(sqlite_info: ConnectionInfo):
    model = parse_db(sqlite_info, SchemaConfig(), LOGGER)
    orders = model.schemas["main"].objects["orders"]

    uniques = orders.get_unique_constrait()
    assert uniques is not None
    assert {frozenset(cluster) for cluster in uniques} == {
        frozenset({"id", "seq"}),
        frozenset({"user_id", "seq"}),
    }

    foreign_keys = list(orders.foreign_keys.values())
    assert len(foreign_keys) == 1
    assert foreign_keys[0].columns == ["user_id"]
    assert foreign_keys[0].ref_table == "users"
    assert foreign_keys[0].ref_columns == ["id"]
    assert foreign_keys[0].on_delete == "CASCADE"

    checks = {check.column: check.definition for check in orders.check_constraints.values()}
    assert checks == {
        "total": "total > 0",
        None: "start_date <= end_date",
    }


def test_parse_db_filtered_unique_index(sqlite_info: ConnectionInfo):
    model = parse_db(sqlite_info, SchemaConfig(), LOGGER)
    users = model.schemas["main"].objects["users"]

    assert not users.columns["code"].is_unique

    filtered = users.filtered_unique_indexes["ux_users_code"]
    assert filtered.columns == ["code"]
    assert filtered.definition == "code IS NOT NULL"

    uniques = users.get_unique_constrait() or []
    assert frozenset({"code"}) not in {frozenset(cluster) for cluster in uniques}


def test_parse_db_respects_schema_config(sqlite_info: ConnectionInfo):
    schema_conf = SchemaConfig()
    schema_conf.exclude_objects("main", {"orders", "v_users"})

    model = parse_db(sqlite_info, schema_conf, LOGGER)
    assert list(model.schemas["main"].objects) == ["users"]


class _UnreflectableInspector:
    def get_pk_constraint(self, name, schema=None):
        return {"name": "pk_users", "constrained_columns": ["id"]}

    def get_indexes(self, name, schema=None):
        return []

    def get_columns(self, name, schema=None):
        return [{"name": "id"}, {"name": "age"}, {"name": "email"}]

    def get_unique_constraints(self, name, schema=None):
        raise NotImplementedError

    def get_check_constraints(self, name, schema=None):
        raise NotImplementedError


class _FallbackHandler:
    def __init__(
        self,
        dialect: type[DialectMap[Any]],
        results: dict[str, pd.DataFrame],
        raw_result: pd.DataFrame | None = None,
    ):
        self._connection_info = SimpleNamespace(dialect=dialect)
        self._results = results
        self._raw_result = pd.DataFrame() if raw_result is None else raw_result
        self.executed: list = []

    def get_connection_info(self):
        return self._connection_info

    def get_inspector(self):
        return _UnreflectableInspector()

    def run_sql(self, sql):
        sql.process_query()
        self.executed.append(sql)

        if sql.sql_path is None:
            return len(self._raw_result), self._raw_result

        key = "check" if "check_constraints" in str(sql.sql_path) else "unique"
        data = self._results[key]
        return len(data), data


@pytest.fixture
def mssql_fallback_handler() -> _FallbackHandler:
    return _FallbackHandler(MssqlMap, {
        "unique": pd.DataFrame({
            "constraint_name": ["uq_users_pair", "uq_users_pair", "uq_users_email"],
            "column_name": ["id", "age", "email"],
        }),
        "check": pd.DataFrame({
            "constraint_name": ["ck_users_age"],
            "sqltext": ["([age]>=(18))"],
        }),
    })


def test_unique_constraints_fallback_on_mssql(mssql_fallback_handler: _FallbackHandler):
    extractor = MetadataExtractor(cast(EngineHandler, mssql_fallback_handler))

    clusters = extractor.list_unique_clusters("dbo", "users")
    by_name = dict(zip(clusters["key_name"], clusters["columns"]))
    assert by_name["uq_users_pair"] == "id, age"
    assert clusters.loc[clusters["key_name"] == "uq_users_pair", "index_type"].iloc[0] == "UNIQUE CONSTRAINT"

    assert extractor._get_single_column_uniques("dbo", "users") == {"email"}

    parameters = {sql.query_parameters["object_name"] for sql in mssql_fallback_handler.executed}
    assert parameters == {"users"}

    for sql in mssql_fallback_handler.executed:
        assert ":schema_name" in sql.processed_query
        assert ":object_name" in sql.processed_query


def test_check_constraints_fallback_on_mssql(mssql_fallback_handler: _FallbackHandler):
    extractor = MetadataExtractor(cast(EngineHandler, mssql_fallback_handler))

    checks = extractor.list_check_constraints("dbo", "users")
    assert checks["check_name"].tolist() == ["ck_users_age"]
    assert checks["definition"].tolist() == ["([age]>=(18))"]
    assert checks["column_name"].tolist() == ["age"]


def test_fallback_degrades_to_empty_without_dialect_sql():
    handler = _FallbackHandler(OracleMap, {})
    extractor = MetadataExtractor(cast(EngineHandler, handler))

    assert extractor.list_check_constraints("app", "users").empty
    assert extractor._get_single_column_uniques("app", "users") == set()
    assert handler.executed == []


def test_parse_db_names_the_database_the_objects_live_in(sqlite_info: ConnectionInfo, tmp_path: Path):
    model = parse_db(sqlite_info, SchemaConfig(), LOGGER)

    assert model.name == str(tmp_path / "fixture.db")


def test_current_database_is_none_without_a_named_database():
    engine = sqlalchemy.create_engine("sqlite://")
    handler = EngineHandler(engine, ConnectionInfo(sqlalchemy.make_url("sqlite://")))

    assert MetadataExtractor(handler).current_database() is None


def test_current_database_ignores_the_url_and_asks_the_connection():
    url = sqlalchemy.make_url("mssql+pyodbc://host/master")
    handler = _FallbackHandler(MssqlMap, {}, pd.DataFrame({"": ["sales_db"]}))

    assert url.database == "master"
    assert MetadataExtractor(cast(EngineHandler, handler)).current_database() == "sales_db"
    assert handler.executed[0].raw_query == "SELECT DB_NAME()"


@pytest.mark.parametrize("dialect", list(DIALECT_MAPS))
def test_every_dialect_can_be_asked_for_its_database(dialect: type[DialectMap[Any]]):
    handler = _FallbackHandler(dialect, {}, pd.DataFrame({"": ["some_db"]}))

    assert MetadataExtractor(cast(EngineHandler, handler)).current_database() == "some_db"
