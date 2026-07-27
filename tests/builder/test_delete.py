import pytest

from alchemy_kit.builder import (
    DeleteBuilder,
    InsertBuilder,
    SelectBuilder,
    TempBuilder,
    TruncateBuilder,
)
from alchemy_kit.connect._engine_handler import EngineHandler

from _helpers import MSSQL_HANDLER, SQLITE_HANDLER, items, mssql_items


def test_delete_render_and_parameters():
    i = SQLITE_HANDLER.get_unit(items)
    builder = DeleteBuilder(i).where(i.price > 1)
    rendered = builder.render()

    assert "DELETE FROM" in rendered
    assert "WHERE" in rendered

    parameters = builder.to_sql().query_parameters
    assert isinstance(parameters, dict)
    assert parameters.items() >= {"price_1": 1}.items()


def test_delete_without_where_removes_every_row():
    i = SQLITE_HANDLER.get_unit(items)
    rendered = DeleteBuilder(i).render()

    assert "DELETE FROM" in rendered
    assert "WHERE" not in rendered


def test_delete_conditions_are_anded():
    i = SQLITE_HANDLER.get_unit(items)
    builder = DeleteBuilder(i).where(i.price > 1, i.id_1 < 5)

    assert "AND" in builder.render()


def test_delete_builder_is_immutable():
    i = SQLITE_HANDLER.get_unit(items)
    base = DeleteBuilder(i)
    filtered = base.where(i.price > 1)

    assert "WHERE" not in base.render()
    assert "WHERE" in filtered.render()


def test_delete_rejects_aliased_unit():
    with pytest.raises(TypeError):
        DeleteBuilder(SQLITE_HANDLER.get_unit(items).set_alias("x"))


def test_truncate_rejects_aliased_unit():
    with pytest.raises(TypeError):
        TruncateBuilder(SQLITE_HANDLER.get_unit(items).set_alias("x"))


def test_truncate_renders_truncate_table():
    i = MSSQL_HANDLER.get_unit(mssql_items)
    rendered = TruncateBuilder(i).render()

    assert rendered == "TRUNCATE TABLE dbo.items"


def test_truncate_renders_delete_on_sqlite():
    i = SQLITE_HANDLER.get_unit(items)
    rendered = TruncateBuilder(i).render()

    assert rendered == "DELETE FROM main.items"


def test_mixing_engine_handlers_raises(handler: EngineHandler):
    i = handler.get_unit(items)
    o = SQLITE_HANDLER.get_unit(items)

    with pytest.raises(ValueError):
        DeleteBuilder(i).where(o.price > 1)


def _staged_items(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values(id_1=1, name="bolt", price=0.5).run()
    InsertBuilder(t).from_values(id_1=2, name="nut", price=1.5).run()
    return t


def test_delete_runs_and_reports_row_count(handler: EngineHandler):
    t = _staged_items(handler)

    count, data = DeleteBuilder(t).where(t.price > 1).run()

    assert count == 1
    assert data.empty

    _, df = SelectBuilder(t.name, from_=t).run()
    assert df["name"].tolist() == ["bolt"]


def test_truncate_runs_and_clears_table(handler: EngineHandler):
    t = _staged_items(handler)

    TruncateBuilder(t).run()

    _, df = SelectBuilder(from_=t).run()
    assert df.empty
