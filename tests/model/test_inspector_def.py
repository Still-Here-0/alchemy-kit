import logging
from pathlib import Path

import pytest
import sqlalchemy

from alchemy_kit.connect._info import ConnectionInfo
from alchemy_kit.model._schema_config import SchemaConfig
from alchemy_kit.model._utils import parse_db
from alchemy_kit.resources._better_logger import BetterLogger

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

    orders = model.schemas["main"].objects["orders"]
    assert orders.columns["id"].is_primary_key
    assert orders.columns["seq"].is_primary_key
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
