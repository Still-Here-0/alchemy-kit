import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest
import sqlalchemy

from alchemy_kit.connect._engine_handler import EngineHandler
from alchemy_kit.connect._info import ConnectionInfo
from alchemy_kit.model._builders import build_model
from alchemy_kit.model._model.db_model import DBModel
from alchemy_kit.model._model.procedure_model import ParameterModel, ProcedureModel
from alchemy_kit.model._model.schema_model import SchemaModel
from alchemy_kit.model.callable_model import CallableModel, CallMetaData
from alchemy_kit.model.units import CallableUnit
from alchemy_kit.resources._better_logger import BetterLogger
from alchemy_kit.types.dialect_types import DialectTypes

MSSQL = EngineHandler(cast(Any, None), ConnectionInfo(sqlalchemy.make_url("mssql+pyodbc://")))
MYSQL = EngineHandler(cast(Any, None), ConnectionInfo(sqlalchemy.make_url("mysql+pymysql://")))
SQLITE = EngineHandler(cast(Any, None), ConnectionInfo(sqlalchemy.make_url("sqlite://")))


def _procedure(name: str, params: list[tuple[str, str, bool]]) -> ProcedureModel:
    procedure = ProcedureModel(name=name, description=None)
    for ordinal, (param_name, param_type, nullable) in enumerate(params, start=1):
        procedure.add_parameter(
            ParameterModel(
                name=param_name,
                parameter_type=param_type,
                is_nullable=nullable,
                mode="IN",
                ordinal=ordinal,
            )
        )
    return procedure


def _db_model(procedure: ProcedureModel) -> DBModel:
    model = DBModel("testdb", DialectTypes.MSSQL)
    schema = SchemaModel("dbo")
    schema.callables[procedure.name] = procedure
    model.schemas["dbo"] = schema
    return model


def _import(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_model_generates_callable_module(tmp_path: Path):
    procedure = _procedure("sync_orders", [("p_id", "int", False), ("p_note", "varchar", True)])
    build_model(_db_model(procedure), tmp_path, BetterLogger(None))

    py_path = tmp_path / "dbo" / "sync_orders_CALL.py"
    pyi_path = tmp_path / "dbo" / "sync_orders_CALL.pyi"
    assert py_path.exists() and pyi_path.exists()

    init_text = (tmp_path / "dbo" / "__init__.py").read_text()
    assert "from .sync_orders_CALL import sync_orders" in init_text

    py_text = py_path.read_text()
    assert "class sync_orders(CallableModel[MssqlTypeParameters]):" in py_text
    assert "reference_name='[dbo].[sync_orders]'" in py_text
    assert "'name': 'p_id'" in py_text and "'mode': 'IN'" in py_text

    pyi_text = pyi_path.read_text()
    assert "class sync_orders_Unit(CallableUnit[MssqlTypeParameters]):" in pyi_text
    assert "def run(self, p_id: int, p_note: Optional[str]) -> tuple[int | None, DataFrame]:" in pyi_text
    assert "def to_sql(self, p_id: int, p_note: Optional[str]) -> SQL:" in pyi_text
    assert "def render(self, p_id: int, p_note: Optional[str]) -> str:" in pyi_text

    for path in tmp_path.rglob("*.py*"):
        compile(path.read_text(), str(path), "exec")


def test_generated_callable_is_callable_via_handler(tmp_path: Path):
    procedure = _procedure("sync_orders", [("p_id", "int", False), ("p_note", "varchar", True)])
    build_model(_db_model(procedure), tmp_path, BetterLogger(None))

    module = _import(tmp_path / "dbo" / "sync_orders_CALL.py", "sync_orders_CALL")

    unit = MSSQL.get_unit(module.sync_orders)
    assert isinstance(unit, CallableUnit)

    assert unit.render(1, "note") == "EXEC [dbo].[sync_orders] :p0, :p1"
    assert unit.to_sql(1, "note").query_parameters == {"p0": 1, "p1": "note"}


def test_no_parameter_procedure(tmp_path: Path):
    build_model(_db_model(_procedure("refresh", [])), tmp_path, BetterLogger(None))

    py_text = (tmp_path / "dbo" / "refresh_CALL.py").read_text()
    pyi_text = (tmp_path / "dbo" / "refresh_CALL.pyi").read_text()

    assert "parameters=[]" in py_text
    assert "def run(self) -> tuple[int | None, DataFrame]:" in pyi_text

    module = _import(tmp_path / "dbo" / "refresh_CALL.py", "refresh_CALL")
    assert MSSQL.get_unit(module.refresh).render() == "EXEC [dbo].[refresh]"


class _sync(CallableModel[str]):
    class Config(CallableModel.Config):
        metadata = CallMetaData(
            schema_name="app",
            name="sync",
            reference_name="`app`.`sync`",
            description=None,
            parameters=[],
        )


def test_handler_get_unit_returns_callable_unit():
    assert isinstance(MYSQL.get_unit(_sync), CallableUnit)


def test_mysql_renders_call_keyword():
    assert MYSQL.get_unit(_sync).render(1, "x") == "CALL `app`.`sync`(:p0, :p1)"


def test_sqlite_call_raises():
    with pytest.raises(ValueError):
        SQLITE.get_unit(_sync).render(1)


def test_render_varies_with_arguments():
    unit = MYSQL.get_unit(_sync)
    assert unit.render(1) != unit.render(1, 2)
