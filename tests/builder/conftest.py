import pytest
import sqlalchemy

from alchemy_kit.connect._engine_handler import EngineHandler
from alchemy_kit.connect._info import ConnectionInfo


@pytest.fixture
def handler():
    engine = sqlalchemy.create_engine("sqlite://")
    return EngineHandler(engine, ConnectionInfo(sqlalchemy.make_url("sqlite://")))
