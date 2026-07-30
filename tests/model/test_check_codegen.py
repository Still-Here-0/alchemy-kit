import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from alchemy_kit.model._builders._build_py_file import PyFileBuilder
from alchemy_kit.model._model.column_model import ColumnModel
from alchemy_kit.model._model.constraint_model import CheckConstraintModel, FilteredUniqueIndexModel
from alchemy_kit.model._model.object_model import ObjectModel
from alchemy_kit.types.dialect_types import DialectTypes
from alchemy_kit.types.errors import ModelValidationError


def _column(name: str, column_type: str, *, nullable: bool = False) -> ColumnModel:
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
        is_foreign_key=False,
        description=None,
        fk_ref=None,
    )


@pytest.fixture
def orders_model() -> ObjectModel:
    obj = ObjectModel("orders", "Table", None)
    for column in [
        _column("id", "int"),
        _column("price", "decimal"),
        _column("status", "varchar"),
        _column("code", "varchar", nullable=True),
        _column("slot", "int", nullable=True),
        _column("start_date", "date", nullable=True),
        _column("end_date", "date", nullable=True),
    ]:
        obj.columns[column.name] = column

    obj.check_constraints = {
        "CK_orders_price": CheckConstraintModel("CK_orders_price", "([price]>(0.00))", "price"),
        "CK_orders_status": CheckConstraintModel("CK_orders_status", "([status] IN ('open','closed'))", "status"),
        "CK_orders_weird": CheckConstraintModel("CK_orders_weird", "(len([status])>(2))", "status"),
        "CK_orders_dates": CheckConstraintModel("CK_orders_dates", "([start_date]<=[end_date])", None),
        "CK_orders_odd": CheckConstraintModel("CK_orders_odd", "([price]%(2)=(1))", None),
    }
    obj.filtered_unique_indexes = {
        "UX_orders_code": FilteredUniqueIndexModel("UX_orders_code", ["code"], "([code] IS NOT NULL)"),
        "UX_orders_slot": FilteredUniqueIndexModel("UX_orders_slot", ["slot"], "([status]=('open'))"),
        "UX_orders_active": FilteredUniqueIndexModel("UX_orders_active", ["status"], "([is_active]=(1))"),
    }
    return obj


def _build(orders_model: ObjectModel, tmp_path: Path) -> str:
    builder = PyFileBuilder(
        db_name="app_db",
        schema_name="dbo",
        class_name="orders",
        file_path=tmp_path / "orders_MODULE.py",
        object_model=orders_model,
        db_dialect=DialectTypes.MSSQL,
    )
    return builder.build()


def _load(tmp_path: Path):
    spec = importlib.util.spec_from_file_location("orders_MODULE", tmp_path / "orders_MODULE.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_file_contains_check_artifacts(orders_model: ObjectModel, tmp_path: Path):
    file_data = _build(orders_model, tmp_path)

    assert "gt=0.0" in file_data
    assert "isin=['open', 'closed']" in file_data
    assert "@pa.dataframe_check(description='CK_orders_dates')" in file_data
    assert "'check_constraints': {'CK_orders_weird': '(len([status])>(2))'}" in file_data
    assert "unparsed_checks={'CK_orders_odd': '([price]%(2)=(1))'}" in file_data
    assert "@pa.dataframe_check(description='UX_orders_code')" in file_data
    assert "masked = df[df['code'].notna()]" in file_data
    assert "~masked.duplicated(subset=['code'], keep=False).reindex(df.index, fill_value=False)" in file_data
    assert "@pa.dataframe_check(description='UX_orders_slot')" in file_data
    assert "masked = df[(df['status'] == 'open')]" in file_data
    assert "~masked.duplicated(subset=['slot'], keep=False).reindex(df.index, fill_value=False)" in file_data
    assert "unparsed_indexes={'UX_orders_active': 'UNIQUE (status) WHERE ([is_active]=(1))'}" in file_data
    compile(file_data, "orders_MODULE.py", "exec")


def test_generated_checks_validate(orders_model: ObjectModel, tmp_path: Path):
    _build(orders_model, tmp_path)
    module = _load(tmp_path)

    good = pd.DataFrame({
        "id": [1, 2, 3],
        "price": [10.0, 5.5, 1.0],
        "status": ["open", "closed", "open"],
        "code": ["A", None, None],
        "slot": [1, 1, 2],
        "start_date": pd.to_datetime(pd.Series(["2026-01-01", None, None])),
        "end_date": pd.to_datetime(pd.Series(["2026-02-01", None, None])),
    })
    module.orders.validate(good)

    bad_frames = [
        good.assign(price=[10.0, -1.0, 1.0]),
        good.assign(status=["open", "nope", "open"]),
        good.assign(start_date=pd.to_datetime(pd.Series(["2026-03-01", None, None]))),
        good.assign(code=pd.Series(["A", "A", None])),
        good.assign(slot=[1, 2, 1]),
    ]
    for bad in bad_frames:
        with pytest.raises(ModelValidationError):
            module.orders.validate(bad)


def test_no_checks_generates_clean_file(tmp_path: Path):
    obj = ObjectModel("plain", "Table", None)
    obj.columns["id"] = _column("id", "int")

    builder = PyFileBuilder(
        db_name="app_db",
        schema_name="dbo",
        class_name="plain",
        file_path=tmp_path / "plain_MODULE.py",
        object_model=obj,
        db_dialect=DialectTypes.MSSQL,
    )
    file_data = builder.build()

    assert ":checks" not in file_data
    assert "dataframe_check" not in file_data
    assert "unparsed_checks" not in file_data
    assert "unparsed_indexes" not in file_data
    compile(file_data, "plain_MODULE.py", "exec")
