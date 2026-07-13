from pathlib import Path
from typing import Iterator

import pandas as pd
import pandera.pandas as pa
import pytest
import sqlalchemy
from pandera.typing import Series

from alchemy_kit.connect._engine_handler import EngineHandler
from alchemy_kit.connect._engine_manager import EngineManager
from alchemy_kit.connect._info import ConnectionInfo
from alchemy_kit.model.base_model import BaseModel, MetaData
from alchemy_kit.types.errors import ModelValidationError


class orders(BaseModel):
    id_1: Series[int] = pa.Field(nullable=False, alias="id")
    user_id: Series[int] = pa.Field(
        nullable=False,
        alias="user_id",
        metadata={"foreign_key": {"schema": "main", "table": "users", "column": "id"}},
    )

    class Config(BaseModel.Config):
        metadata = MetaData(
            schema_name="main",
            obj_name="orders",
            obj_type="Table",
            reference_name="main.orders",
            description=None,
        )


@pytest.fixture
def handler(tmp_path: Path) -> Iterator[EngineHandler]:
    db_path = tmp_path / "fk.db"

    engine = sqlalchemy.create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        conn.exec_driver_sql("INSERT INTO users (id) VALUES (1), (2), (3)")
    engine.dispose()

    info = ConnectionInfo(sqlalchemy.URL.create("sqlite", database=str(db_path)), "fk-test")
    with EngineManager(None) as manager:
        yield manager.create_engine(info)


def test_iter_foreign_keys():
    assert list(orders.iter_foreign_keys()) == [
        ("user_id", {"schema": "main", "table": "users", "column": "id"}),
    ]


def test_validate_foreign_keys_passes(handler: EngineHandler):
    good = pd.DataFrame({"id": [10, 11], "user_id": [1, 3]})

    assert orders.validate_foreign_keys(good, handler) == {}
    orders.validate(good, handler=handler)


def test_validate_foreign_keys_reports_missing(handler: EngineHandler):
    bad = pd.DataFrame({"id": [10, 11, 12], "user_id": [1, 99, 42]})

    assert orders.validate_foreign_keys(bad, handler) == {"user_id": {42, 99}}

    with pytest.raises(ModelValidationError, match="user_id"):
        orders.validate(bad, handler=handler)


def test_validate_without_handler_stays_offline():
    bad = pd.DataFrame({"id": [10], "user_id": [99]})
    validated = orders.validate(bad)
    assert validated.shape == (1, 2)
