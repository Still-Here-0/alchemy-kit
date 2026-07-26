import shutil
from pathlib import Path
from typing import cast

import pytest

from alchemy_kit.connect._info import ConnectionInfo
from alchemy_kit.connect import info_builder
from alchemy_kit.model import build
from alchemy_kit.model import _builder
from alchemy_kit.model._model.column_model import ColumnModel, ForeignKeyModel
from alchemy_kit.model._model.constraint_model import CheckConstraintModel, FilteredUniqueIndexModel
from alchemy_kit.model import SchemaConfig
from alchemy_kit.model._model.db_model import DBModel
from alchemy_kit.model._model.object_model import ObjectModel
from alchemy_kit.model._model.schema_model import SchemaModel
from alchemy_kit.types.dialect_types import DialectTypes


ROOT = Path(__file__).resolve().parent.parent
PREVIEW_DIR = ROOT / "secret_model_preview"

def _column(name: str, column_type: str, *, nullable: bool = False, fk_ref: ForeignKeyModel | None = None) -> ColumnModel:
    return ColumnModel(
        name=name,
        column_type=column_type,
        is_nullable=nullable,
        is_identity=False,
        is_computed=False,
        max_length=None,
        precision=None,
        scale=None,
        collation_name=None,
        has_default=False,
        default=None,
        is_unique=False,
        is_primary_key=False,
        is_foreign_key=fk_ref is not None,
        description=None,
        fk_ref=fk_ref,
    )

def _object(name: str, columns: list[ColumnModel]) -> ObjectModel:
    obj = ObjectModel(name, "Table", None)
    for column in columns:
        obj.columns[column.name] = column
    return obj

def _fake_model() -> DBModel:
    model = DBModel("testdb", DialectTypes.MSSQL)

    dbo = SchemaModel("dbo")
    dbo.objects["users"] = _object("users", [_column("id", "int"), _column("email", "varchar", nullable=True)])

    orders = _object("orders", [
        _column("id", "int"),
        _column("total", "decimal"),
        _column("status", "varchar"),
        _column("start_date", "date", nullable=True),
        _column("end_date", "date", nullable=True),
        _column("user_id", "int", fk_ref=ForeignKeyModel(schema="dbo", table="users", column="id")),
    ])
    orders.add_unique_constrait(["id", "user_id"])
    orders.check_constraints = {
        "CK_orders_total": CheckConstraintModel("CK_orders_total", "([total]>(0.00))", "total"),
        "CK_orders_status": CheckConstraintModel("CK_orders_status", "([status] IN ('open','closed'))", "status"),
        "CK_orders_len": CheckConstraintModel("CK_orders_len", "(len([status])>(2))", "status"),
        "CK_orders_dates": CheckConstraintModel("CK_orders_dates", "([start_date]<=[end_date])", None),
        "CK_orders_odd": CheckConstraintModel("CK_orders_odd", "([total]%(2)=(1))", None),
    }
    orders.filtered_unique_indexes = {
        "UX_orders_status": FilteredUniqueIndexModel("UX_orders_status", ["status"], "([status] IS NOT NULL)"),
    }
    dbo.objects["orders"] = orders

    audit = SchemaModel("audit")
    audit.objects["users"] = _object("users", [_column("id", "int")])

    model.schemas["dbo"] = dbo
    model.schemas["audit"] = audit
    return model

def test_build_generates_package(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(_builder, "parse_db", lambda *args, **kwargs: _fake_model())

    shutil.rmtree(PREVIEW_DIR, ignore_errors=True)
    result_dir = PREVIEW_DIR
    build(cast(ConnectionInfo, None), result_dir)

    assert (result_dir / "__init__.py").exists()
    for schema in ("dbo", "audit"):
        assert (result_dir / schema / "__init__.py").exists()

    for module in ("users_MODULE", "orders_MODULE"):
        assert (result_dir / "dbo" / f"{module}.py").exists()
        assert (result_dir / "dbo" / f"{module}.pyi").exists()

    assert (result_dir / "audit" / "users_MODULE.py").exists()
    assert (result_dir / "audit" / "users_MODULE.pyi").exists()

    assert (result_dir / "dbo" / "__init__.py").read_text().splitlines() == [
        "from .users_MODULE import users",
        "from .orders_MODULE import orders",
    ]
    assert (result_dir / "audit" / "__init__.py").read_text().strip() == "from .users_MODULE import users"

    orders_py = (result_dir / "dbo" / "orders_MODULE.py").read_text()
    assert "gt=0.0" in orders_py
    assert "isin=['open', 'closed']" in orders_py
    assert "@pa.dataframe_check(description='CK_orders_dates')" in orders_py
    assert "'check_constraints': {'CK_orders_len': '(len([status])>(2))'}" in orders_py
    assert "unparsed_checks={'CK_orders_odd': '([total]%(2)=(1))'}" in orders_py
    assert "'foreign_key': {'schema': 'dbo', 'table': 'users', 'column': 'id'}" in orders_py
    assert "@pa.dataframe_check(description='UX_orders_status')" in orders_py
    assert "masked = df[df['status'].notna()]" in orders_py

    unique_line = next(line for line in orders_py.splitlines() if line.strip().startswith("unique=[["))
    assert "'id'" in unique_line and "'user_id'" in unique_line

    for path in result_dir.rglob("*.py*"):
        compile(path.read_text(), str(path), "exec")

@pytest.mark.local
def test_mssql_local_build():
    conn = info_builder.from_env(ROOT/".env-mssql")
    config = SchemaConfig()
    config.include_schema("uploader")
    build(conn, ROOT/"model"/"secret_local_mssql", schema_config=config, clear_result_dir=True)
    from alchemy_kit import builder
    from secret_local_mssql.uploader import SHEET
    from alchemy_kit.connect import EngineManager
    with EngineManager(None) as manager:
        handler = manager.create_engine(conn)
        sheet = handler.get_unit(SHEET)
        select = builder.SelectBuilder(from_=sheet)
        _, df = select.run()
        df = df[[SHEET.Description, SHEET.TableName, SHEET.LastEditedBy_fk, SHEET.Active, SHEET.DaysToRefresh, SHEET.Model, SHEET.RequestAfterUpdate]]
        insert = builder.InsertBuilder(handler.get_unit(SHEET)).from_dataframe(df)
        insert.run()

