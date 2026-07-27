import pytest

from alchemy_kit.builder import InsertBuilder, SelectBuilder, TempBuilder, UpdateBuilder
from alchemy_kit.connect._engine_handler import EngineHandler

from _helpers import SQLITE_HANDLER, items


def test_update_render_and_parameters():
    i = SQLITE_HANDLER.get_unit(items)
    builder = UpdateBuilder(i).set_values((i.id_1, 7), (i.name, "bolt")).where(i.price > 1)
    rendered = builder.render()

    assert "UPDATE" in rendered
    assert "SET id=:id, name=:name" in rendered
    assert "WHERE" in rendered

    parameters = builder.to_sql().query_parameters
    assert isinstance(parameters, dict)
    assert parameters.items() >= {"id": 7, "name": "bolt", "price_1": 1}.items()


def test_update_sets_column_expression():
    i = SQLITE_HANDLER.get_unit(items)
    rendered = UpdateBuilder(i).set_values((i.price, i.price * 2)).render()

    assert "SET price=(main.items.price * :price_1)" in rendered


def test_update_resolves_units_to_columns():
    i = SQLITE_HANDLER.get_unit(items)
    rendered = UpdateBuilder(i).set_values((i.id_1, 1)).render()

    assert "SET id=:id" in rendered
    assert "id_1" not in rendered


def test_update_builder_is_immutable():
    i = SQLITE_HANDLER.get_unit(items)
    base = UpdateBuilder(i).set_values((i.name, "bolt"))
    filtered = base.where(i.price > 1)

    assert "WHERE" not in base.render()
    assert "WHERE" in filtered.render()


def test_update_conditions_are_anded():
    i = SQLITE_HANDLER.get_unit(items)
    builder = UpdateBuilder(i).set_values((i.name, "bolt")).where(i.price > 1, i.id_1 < 5)

    assert "AND" in builder.render()


def test_update_rejects_aliased_unit():
    with pytest.raises(TypeError):
        UpdateBuilder(SQLITE_HANDLER.get_unit(items).set_alias("x"))


def test_update_rejects_condition_as_value():
    i = SQLITE_HANDLER.get_unit(items)
    with pytest.raises(TypeError):
        UpdateBuilder(i).set_values((i.price, i.price > 1))  # pyright: ignore[reportArgumentType]


def test_mixing_engine_handlers_raises(handler: EngineHandler):
    i = handler.get_unit(items)
    o = SQLITE_HANDLER.get_unit(items)

    with pytest.raises(ValueError):
        UpdateBuilder(i).set_values((i.name, "bolt")).where(o.price > 1)
    with pytest.raises(ValueError):
        UpdateBuilder(i).set_values((i.price, o.price * 2))
    with pytest.raises(ValueError):
        UpdateBuilder(i).set_values((o.price, 1.0))


def _staged_items(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values((t.id_1, 1), (t.name, "bolt"), (t.price, 0.5)).run()
    InsertBuilder(t).from_values((t.id_1, 2), (t.name, "nut"), (t.price, 1.5)).run()
    return t


def test_update_runs_and_reports_row_count(handler: EngineHandler):
    t = _staged_items(handler)

    count, data = UpdateBuilder(t).set_values((t.price, 9.0)).where(t.name == "bolt").run()

    assert count == 1
    assert data.empty

    _, df = SelectBuilder(t.name, t.price, from_=t).order_by(t.id_1).run()
    assert df["price"].tolist() == [9.0, 1.5]


def test_update_runs_column_expression(handler: EngineHandler):
    t = _staged_items(handler)

    UpdateBuilder(t).set_values((t.price, t.price * 2), (t.name, t.name.upper())).run()

    _, df = SelectBuilder(t.name, t.price, from_=t).order_by(t.id_1).run()
    assert df["price"].tolist() == [1.0, 3.0]
    assert df["name"].tolist() == ["BOLT", "NUT"]


def test_update_without_where_rewrites_every_row(handler: EngineHandler):
    t = _staged_items(handler)

    count, _ = UpdateBuilder(t).set_values((t.price, 0.0)).run()

    assert count == 2

    _, df = SelectBuilder(t.price, from_=t).run()
    assert df["price"].tolist() == [0.0, 0.0]
