from typing import Any

import pytest

from alchemy_kit.builder import InsertBuilder, SelectBuilder, TempBuilder
from alchemy_kit.connect._engine_handler import EngineHandler
from alchemy_kit.model.units import OperandUnit
from alchemy_kit.resources.dialect_map import get_sa_dialect
from alchemy_kit.types.dialect_types import DialectTypes
from alchemy_kit.types.errors import StatementLimitError

from _helpers import MSSQL_HANDLER, SQLITE_HANDLER, items, mssql_items, parts


def test_every_dialect_compiles_with_named_paramstyle():
    for dialect in DialectTypes:
        assert get_sa_dialect(dialect).paramstyle == "named"


def test_select_render_and_parameters():
    i = SQLITE_HANDLER.get_unit(items)
    builder = (
        SelectBuilder(i.name, i.price.sum().set_alias("total"), from_=i)
        .where(i.price > 1)
        .group_by(i.name)
        .having(i.price.sum() > 2)
        .order_by(i.price.sum().desc())
        .limit(5)
    )
    rendered = builder.render()

    assert "GROUP BY" in rendered and "HAVING" in rendered and "ORDER BY" in rendered

    parameters = builder.to_sql().query_parameters
    assert isinstance(parameters, dict)
    assert parameters.items() >= {"price_1": 1, "sum_1": 2, "param_1": 5}.items()


def test_select_builder_is_immutable():
    i = SQLITE_HANDLER.get_unit(items)
    base = SelectBuilder(i.name, from_=i)
    filtered = base.where(i.price > 1)

    assert "WHERE" not in base.render()
    assert "WHERE" in filtered.render()


def test_cross_join_compiles_and_runs(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values((t.id_1, 1), (t.name, "bolt"), (t.price, 0.5)).run()
    InsertBuilder(t).from_values((t.id_1, 2), (t.name, "nut"), (t.price, 1.5)).run()

    o = tmp.unit().set_alias("o")
    builder = SelectBuilder(t.name, o.price, from_=t).join("CROSS", o)
    assert "ON 1 = 1" in builder.render()

    _, df = builder.run()
    assert len(df) == 4


def test_right_join_keeps_unmatched_right_rows(handler: EngineHandler):
    items_tmp = TempBuilder(handler.get_unit(items))
    items_tmp.run()
    parts_tmp = TempBuilder(handler.get_unit(parts))
    parts_tmp.run()

    t, p = items_tmp.unit(), parts_tmp.unit()
    InsertBuilder(t).from_values((t.id_1, 1), (t.name, "bolt"), (t.price, 0.5)).run()
    InsertBuilder(p).from_values((p.id_1, 1), (p.label, "washer")).run()
    InsertBuilder(p).from_values((p.id_1, 2), (p.label, "nut")).run()

    builder = SelectBuilder(t.name, p.id_1, from_=t).join("RIGHT", p, t.id_1 == p.id_1)
    assert "LEFT OUTER JOIN" in builder.render()

    _, df = builder.run()
    assert sorted(df["id"].tolist()) == [1, 2]
    assert df["name"].isna().sum() == 1


def test_joins_chain_after_right(handler: EngineHandler):
    items_tmp = TempBuilder(handler.get_unit(items))
    items_tmp.run()
    parts_tmp = TempBuilder(handler.get_unit(parts))
    parts_tmp.run()

    t, p = items_tmp.unit(), parts_tmp.unit()
    InsertBuilder(t).from_values((t.id_1, 1), (t.name, "bolt"), (t.price, 0.5)).run()
    InsertBuilder(p).from_values((p.id_1, 1), (p.label, "washer")).run()
    InsertBuilder(p).from_values((p.id_1, 2), (p.label, "nut")).run()

    third = parts_tmp.unit().set_alias("third")
    builder = (
        SelectBuilder(t.name, p.id_1, from_=t)
        .join("RIGHT", p, t.id_1 == p.id_1)
        .join("INNER", third, p.id_1 == third.id_1)
    )
    rendered = builder.render()
    assert rendered.count("JOIN") == 2

    _, df = builder.run()
    assert sorted(df["id"].tolist()) == [1, 2]


def test_join_condition_arity():
    i = SQLITE_HANDLER.get_unit(items)
    o = SQLITE_HANDLER.get_unit(items).set_alias("o")
    with pytest.raises(TypeError):
        SelectBuilder(i.name, from_=i).join("CROSS", o, i.id_1 == o.id_1)
    with pytest.raises(TypeError):
        SelectBuilder(i.name, from_=i).join("INNER", o)


def test_null_safe_comparisons(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values((t.id_1, 1), (t.name, "bolt"), (t.price, 0.5)).run()
    InsertBuilder(t).from_values((t.id_1, 2), (t.name, "nut"), (t.price, None)).run()

    _, df = SelectBuilder(t.name, from_=t).where(t.price != 0.5).run()
    assert df["name"].tolist() == []

    _, df = SelectBuilder(t.name, from_=t).where(t.price.is_distinct_from(0.5)).run()
    assert df["name"].tolist() == ["nut"]

    _, df = SelectBuilder(t.name, from_=t).where(t.price.is_not_distinct_from(None)).run()
    assert df["name"].tolist() == ["nut"]


def test_nullif_guards_division(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values((t.id_1, 1), (t.name, "free"), (t.price, 0.0)).run()
    InsertBuilder(t).from_values((t.id_1, 2), (t.name, "dear"), (t.price, 2.0)).run()

    _, df = SelectBuilder(t.name, (10 / t.price.nullif(0)).set_alias("ratio"), from_=t).run()
    by_name = dict(zip(df["name"], df["ratio"]))
    assert by_name["free"] is None or by_name["free"] != by_name["free"]
    assert by_name["dear"] == 5.0


def test_floor_division(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values((t.id_1, 7), (t.name, "bolt"), (t.price, 4.5)).run()

    builder = SelectBuilder((t.id_1 // 2).set_alias("half"), (100 // t.id_1).set_alias("inverse"), (t.price // 2).set_alias("floored"), from_=t)
    assert "FLOOR" in builder.render()

    _, df = builder.run()
    assert df["half"].tolist() == [3]
    assert df["inverse"].tolist() == [14]
    assert df["floored"].tolist() == [2.0]


def test_string_operations(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values((t.id_1, 1), (t.name, "  Bolt  "), (t.price, 0.5)).run()

    _, df = SelectBuilder(t.name.trim().lower().set_alias("clean"), t.name.trim().upper().set_alias("loud"), t.name.trim().length().set_alias("size"), t.name.trim().concat("-", t.name.trim()).set_alias("doubled"), from_=t).run()

    assert df["clean"].tolist() == ["bolt"]
    assert df["loud"].tolist() == ["BOLT"]
    assert df["size"].tolist() == [4]
    assert df["doubled"].tolist() == ["Bolt-Bolt"]


def test_ordering_unit_null_placement(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values((t.id_1, 1), (t.name, "bolt"), (t.price, 9.0)).run()
    InsertBuilder(t).from_values((t.id_1, 2), (t.name, "nut"), (t.price, None)).run()
    InsertBuilder(t).from_values((t.id_1, 3), (t.name, "gear"), (t.price, 0.5)).run()

    builder = SelectBuilder(t.name, from_=t).order_by(t.price.desc().nulls_last())
    assert "NULLS LAST" in builder.render()

    _, df = builder.run()
    assert df["name"].tolist() == ["bolt", "gear", "nut"]

    _, df = SelectBuilder(t.name, from_=t).order_by(t.price.asc().nulls_first()).run()
    assert df["name"].tolist() == ["nut", "gear", "bolt"]


def test_ordering_unit_is_not_a_value():
    i = SQLITE_HANDLER.get_unit(items)
    with pytest.raises(TypeError):
        _ = i.price.desc() + 1  # pyright: ignore[reportOperatorIssue]
    with pytest.raises(AttributeError):
        i.price.desc().sum()  # pyright: ignore[reportAttributeAccessIssue]


def test_window_running_total(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values((t.id_1, 1), (t.name, "bolt"), (t.price, 10.0)).run()
    InsertBuilder(t).from_values((t.id_1, 2), (t.name, "nut"), (t.price, 25.0)).run()
    InsertBuilder(t).from_values((t.id_1, 3), (t.name, "gear"), (t.price, 5.0)).run()

    builder = SelectBuilder(t.name, t.price.sum().over(order_by=t.id_1.asc()).set_alias("running"), from_=t).order_by(t.id_1)
    assert "OVER (ORDER BY" in builder.render()

    _, df = builder.run()
    assert df["running"].tolist() == [10.0, 35.0, 40.0]


def test_window_partition(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values((t.id_1, 1), (t.name, "bolt"), (t.price, 1.0)).run()
    InsertBuilder(t).from_values((t.id_1, 2), (t.name, "bolt"), (t.price, 2.0)).run()
    InsertBuilder(t).from_values((t.id_1, 3), (t.name, "nut"), (t.price, 5.0)).run()

    builder = SelectBuilder(t.name, (t.price / t.price.sum().over(partition_by=t.name)).set_alias("share"), from_=t).order_by(t.id_1)
    assert "OVER (PARTITION BY" in builder.render()

    _, df = builder.run()
    assert df["share"].tolist() == [1 / 3, 2 / 3, 1.0]


def test_window_row_number_per_group(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values((t.id_1, 1), (t.name, "bolt"), (t.price, 1.0)).run()
    InsertBuilder(t).from_values((t.id_1, 2), (t.name, "bolt"), (t.price, 2.0)).run()
    InsertBuilder(t).from_values((t.id_1, 3), (t.name, "nut"), (t.price, 5.0)).run()

    _, df = SelectBuilder(t.name, OperandUnit.row_number()
        .over(partition_by=t.name, order_by=t.price.desc())
        .set_alias("rn"), from_=t).order_by(t.id_1).run()

    assert df["rn"].tolist() == [2, 1, 1]


def test_operand_rankings(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    for row_id, price in [(1, 10.0), (2, 10.0), (3, 20.0)]:
        InsertBuilder(t).from_values((t.id_1, row_id), (t.name, "bolt"), (t.price, price)).run()

    _, df = SelectBuilder(t.id_1, OperandUnit.rank().over(order_by=t.price.asc()).set_alias("rnk"), OperandUnit.dense_rank().over(order_by=t.price.asc()).set_alias("dense"), OperandUnit.percent_rank().over(order_by=t.price.asc()).set_alias("pct"), OperandUnit.cume_dist().over(order_by=t.price.asc()).set_alias("cume"), from_=t).order_by(t.id_1).run()

    assert df["rnk"].tolist() == [1, 1, 3]
    assert df["dense"].tolist() == [1, 1, 2]
    assert df["pct"].tolist() == [0.0, 0.0, 1.0]
    assert df["cume"].tolist() == [2 / 3, 2 / 3, 1.0]


def test_operand_ntile(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    for row_id in range(1, 5):
        InsertBuilder(t).from_values((t.id_1, row_id), (t.name, "bolt"), (t.price, float(row_id))).run()

    _, df = SelectBuilder(t.id_1, OperandUnit.ntile(2).over(order_by=t.price.asc()).set_alias("bucket"), from_=t).order_by(t.id_1).run()

    assert df["bucket"].tolist() == [1, 1, 2, 2]


def test_operand_count_star_in_first_position(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    for row_id in range(1, 4):
        InsertBuilder(t).from_values((t.id_1, row_id), (t.name, "bolt"), (t.price, 1.0)).run()

    builder = SelectBuilder(OperandUnit.count().over().set_alias("total"), t.name, from_=t).order_by(t.id_1)
    assert "count(*) OVER" in builder.render()

    _, df = builder.run()
    assert df["total"].tolist() == [3, 3, 3]


def test_operand_current_timestamp_is_portable(handler: EngineHandler):
    si = handler.get_unit(items)
    mi = MSSQL_HANDLER.get_unit(mssql_items)
    on_sqlite = SelectBuilder(si.id_1, OperandUnit.current_timestamp().set_alias("now"), from_=si)
    on_mssql = SelectBuilder(mi.id_1, OperandUnit.current_timestamp().set_alias("now"), from_=mi)
    assert "CURRENT_TIMESTAMP" in on_sqlite.render()
    assert "CURRENT_TIMESTAMP" in on_mssql.render()

    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values((t.id_1, 1), (t.name, "bolt"), (t.price, 1.0)).run()
    _, df = SelectBuilder(t.id_1, OperandUnit.current_timestamp().set_alias("now"), from_=t).run()
    assert df["now"].notna().all()


def test_operand_current_date_unsupported_on_mssql():
    si = SQLITE_HANDLER.get_unit(items)
    mi = MSSQL_HANDLER.get_unit(mssql_items)
    assert "CURRENT_DATE" in SelectBuilder(si.id_1, OperandUnit.current_date().set_alias("d"), from_=si).render()
    with pytest.raises(ValueError):
        SelectBuilder(mi.id_1, OperandUnit.current_date().set_alias("d"), from_=mi).render()


def test_operand_niladic_dialect_matrix():
    from alchemy_kit.model.units import _operand_unit as ou

    def rendered(element: Any, dialect: DialectTypes) -> str:
        return str(element.compile(dialect=get_sa_dialect(dialect)))

    D = DialectTypes

    assert rendered(ou._CurrentDate(), D.SQLITE) == "CURRENT_DATE"
    with pytest.raises(ValueError):
        rendered(ou._CurrentDate(), D.MSSQL)

    assert rendered(ou._CurrentTime(), D.POSTGRESQL) == "CURRENT_TIME"
    for d in (D.MSSQL, D.ORACLE):
        with pytest.raises(ValueError):
            rendered(ou._CurrentTime(), d)

    assert rendered(ou._CurrentUser(), D.MSSQL) == "CURRENT_USER"
    assert rendered(ou._CurrentUser(), D.ORACLE) == "USER"
    with pytest.raises(ValueError):
        rendered(ou._CurrentUser(), D.SQLITE)

    assert rendered(ou._SessionUser(), D.POSTGRESQL) == "SESSION_USER"
    assert rendered(ou._SessionUser(), D.MYSQL) == "SESSION_USER()"
    for d in (D.SQLITE, D.ORACLE):
        with pytest.raises(ValueError):
            rendered(ou._SessionUser(), d)


def test_window_lag(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values((t.id_1, 1), (t.name, "bolt"), (t.price, 10.0)).run()
    InsertBuilder(t).from_values((t.id_1, 2), (t.name, "nut"), (t.price, 25.0)).run()

    _, df = SelectBuilder(t.name, (t.price - t.price.lag().over(order_by=t.id_1.asc())).set_alias("change"), t.price.lag(1, default=0.0).over(order_by=t.id_1.asc()).set_alias("previous"), from_=t).order_by(t.id_1).run()

    assert df["change"].isna().tolist() == [True, False]
    assert df["change"].tolist()[1] == 15.0
    assert df["previous"].tolist() == [0.0, 10.0]


def test_window_frame(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    for row_id, price in [(1, 2.0), (2, 4.0), (3, 12.0)]:
        InsertBuilder(t).from_values((t.id_1, row_id), (t.name, "bolt"), (t.price, price)).run()

    builder = SelectBuilder(t.price.avg().over(order_by=t.id_1.asc(), rows=(-1, 0)).set_alias("moving"), from_=t).order_by(t.id_1)
    assert "PRECEDING AND CURRENT ROW" in builder.render()

    _, df = builder.run()
    assert df["moving"].tolist() == [2.0, 3.0, 8.0]


def test_window_function_unit_is_not_a_value():
    i = SQLITE_HANDLER.get_unit(items)
    pending = OperandUnit.row_number()
    with pytest.raises(TypeError):
        _ = pending + 1  # pyright: ignore[reportOperatorIssue]
    with pytest.raises(AttributeError):
        pending.set_alias("rn")  # pyright: ignore[reportAttributeAccessIssue]
    with pytest.raises(AttributeError):
        i.price.lag().sum()  # pyright: ignore[reportAttributeAccessIssue]

    aliased = i.price.sum().set_alias("total")
    assert not hasattr(aliased, "over")


def test_is_in_parses_null(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values((t.id_1, 1), (t.name, "bolt"), (t.price, 0.5)).run()
    InsertBuilder(t).from_values((t.id_1, 2), (t.name, "nut"), (t.price, None)).run()
    InsertBuilder(t).from_values((t.id_1, 3), (t.name, "gear"), (t.price, 9.0)).run()

    builder = SelectBuilder(t.name, from_=t).where(t.price.is_in([0.5, None]))
    rendered = builder.render()
    assert "IS NULL" in rendered and "OR" in rendered

    _, df = builder.run()
    assert sorted(df["name"].tolist()) == ["bolt", "nut"]


def test_not_in_parses_null(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values((t.id_1, 1), (t.name, "bolt"), (t.price, 0.5)).run()
    InsertBuilder(t).from_values((t.id_1, 2), (t.name, "nut"), (t.price, None)).run()
    InsertBuilder(t).from_values((t.id_1, 3), (t.name, "gear"), (t.price, 9.0)).run()

    _, df = SelectBuilder(t.name, from_=t).where(t.price.not_in([0.5, None])).run()
    assert df["name"].tolist() == ["gear"]

    _, raw = SelectBuilder(t.name, from_=t).where(t.price.not_in([0.5, None], parse_null=False)).run()
    assert raw["name"].tolist() == []


def test_is_in_with_only_null(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values((t.id_1, 1), (t.name, "bolt"), (t.price, 0.5)).run()
    InsertBuilder(t).from_values((t.id_1, 2), (t.name, "nut"), (t.price, None)).run()

    builder = SelectBuilder(t.name, from_=t).where(t.price.is_in([None]))
    rendered = builder.render()
    assert "IS NULL" in rendered and "IN" not in rendered.replace("IS NULL", "")

    _, df = builder.run()
    assert df["name"].tolist() == ["nut"]


def test_is_in_raw_null(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values((t.id_1, 1), (t.name, "bolt"), (t.price, 0.5)).run()
    InsertBuilder(t).from_values((t.id_1, 2), (t.name, "nut"), (t.price, None)).run()

    builder = SelectBuilder(t.name, from_=t).where(t.price.is_in([0.5, None], parse_null=False))
    assert "IS NULL" not in builder.render()

    _, df = builder.run()
    assert df["name"].tolist() == ["bolt"]


def test_deferred_parameter_override(handler: EngineHandler):
    tmp = TempBuilder(handler.get_unit(items))
    tmp.run()
    t = tmp.unit()
    InsertBuilder(t).from_values((t.id_1, 1), (t.name, "cheap"), (t.price, 1.0)).run()
    InsertBuilder(t).from_values((t.id_1, 2), (t.name, "dear"), (t.price, 9.0)).run()

    builder = SelectBuilder(t.name, from_=t).where(t.price > 1)
    _, df = builder.run(price_1=8)
    assert df["name"].tolist() == ["dear"]


def test_scalar_subquery_renders_top_on_mssql():
    m = MSSQL_HANDLER.get_unit(mssql_items)
    sub = MSSQL_HANDLER.get_unit(mssql_items).set_alias("sub")
    latest = (
        SelectBuilder(sub.id_1, from_=sub)
        .order_by(sub.id_1.desc())
        .limit(1)
        .as_scalar()
        .set_alias("latest")
    )
    rendered = SelectBuilder(m.id_1, latest, from_=m).render()
    assert "TOP 1" in rendered
    assert "latest" in rendered


def test_scalar_subquery_renders_limit_on_sqlite():
    i = SQLITE_HANDLER.get_unit(items)
    sub = SQLITE_HANDLER.get_unit(items).set_alias("sub")
    latest = SelectBuilder(sub.id_1, from_=sub).order_by(sub.id_1.desc()).limit(1).as_scalar()
    rendered = SelectBuilder(i.name, latest, from_=i).render()
    assert "LIMIT" in rendered
    assert "TOP" not in rendered


def test_scalar_subquery_correlates_on_outer_column():
    i = SQLITE_HANDLER.get_unit(items)
    p = SQLITE_HANDLER.get_unit(parts)
    label = (
        SelectBuilder(p.label, from_=p).where(p.id_1 == i.id_1).limit(1).as_scalar().set_alias("label")
    )
    rendered = SelectBuilder(i.name, label, from_=i).render()
    assert rendered.count("FROM main.items") == 1
    assert "FROM main.parts" in rendered


def test_scalar_subquery_runs(handler: EngineHandler):
    items_tmp = TempBuilder(handler.get_unit(items))
    items_tmp.run()
    parts_tmp = TempBuilder(handler.get_unit(parts))
    parts_tmp.run()

    t, p = items_tmp.unit(), parts_tmp.unit()
    InsertBuilder(t).from_values((t.id_1, 1), (t.name, "bolt"), (t.price, 0.5)).run()
    InsertBuilder(t).from_values((t.id_1, 2), (t.name, "nut"), (t.price, 1.5)).run()
    InsertBuilder(p).from_values((p.id_1, 1), (p.label, "washer")).run()
    InsertBuilder(p).from_values((p.id_1, 2), (p.label, "gear")).run()

    label = (
        SelectBuilder(p.label, from_=p).where(p.id_1 == t.id_1).limit(1).as_scalar().set_alias("label")
    )
    _, df = SelectBuilder(t.name, label, from_=t).order_by(t.id_1).run()
    assert df["label"].tolist() == ["washer", "gear"]


def test_from_subquery_join_renders_derived_table():
    i = SQLITE_HANDLER.get_unit(items)
    p = SQLITE_HANDLER.get_unit(parts)
    active = SelectBuilder(p, from_=p).where(p.id_1 > 1).as_object("p")
    rendered = SelectBuilder(i.name, active.label, from_=i).join(
        "INNER", active, i.id_1 == active.id_1
    ).render()
    assert "JOIN (SELECT" in rendered
    assert ") AS p" in rendered
    assert "WHERE" in rendered


def test_from_subquery_join_runs(handler: EngineHandler):
    items_tmp = TempBuilder(handler.get_unit(items))
    items_tmp.run()
    parts_tmp = TempBuilder(handler.get_unit(parts))
    parts_tmp.run()

    t, p = items_tmp.unit(), parts_tmp.unit()
    InsertBuilder(t).from_values((t.id_1, 1), (t.name, "bolt"), (t.price, 0.5)).run()
    InsertBuilder(t).from_values((t.id_1, 2), (t.name, "nut"), (t.price, 1.5)).run()
    InsertBuilder(p).from_values((p.id_1, 1), (p.label, "washer")).run()
    InsertBuilder(p).from_values((p.id_1, 2), (p.label, "gear")).run()

    active = SelectBuilder(p, from_=p).where(p.id_1 > 1).as_object("p")
    _, df = (
        SelectBuilder(t.name, active.label, from_=t)
        .join("INNER", active, t.id_1 == active.id_1)
        .run()
    )
    assert df["name"].tolist() == ["nut"]
    assert df["label"].tolist() == ["gear"]


def test_paginate_compiles_limit_and_offset():
    i = SQLITE_HANDLER.get_unit(items)
    sql = SelectBuilder(i.name, from_=i).order_by(i.id_1).paginate(3, 20).to_sql()

    assert sql.raw_query is not None
    assert "LIMIT" in sql.raw_query
    assert "OFFSET" in sql.raw_query

    params = sql.query_parameters
    assert isinstance(params, dict)
    assert 20 in params.values()
    assert 40 in params.values()


def test_paginate_runs(handler: EngineHandler):
    items_tmp = TempBuilder(handler.get_unit(items))
    items_tmp.run()

    t = items_tmp.unit()
    for id_1, name in enumerate(["a", "b", "c", "d", "e"], start=1):
        InsertBuilder(t).from_values((t.id_1, id_1), (t.name, name), (t.price, float(id_1))).run()

    def page(number: int) -> list[str]:
        _, df = SelectBuilder(t.name, from_=t).order_by(t.id_1).paginate(number, 2).run()
        return df["name"].tolist()

    assert page(1) == ["a", "b"]
    assert page(2) == ["c", "d"]
    assert page(3) == ["e"]


def test_oversized_is_in_list_raises_before_the_server_does():
    i = MSSQL_HANDLER.get_unit(mssql_items)
    select = SelectBuilder(i.id_1, from_=i).where(i.id_1.is_in(list(range(3000))))

    with pytest.raises(StatementLimitError) as error:
        select.to_sql()

    assert error.value.needed == 3000
    assert error.value.budget == 2098
    assert "TempBuilder" in str(error.value)


def test_statement_at_the_parameter_budget_still_compiles():
    i = MSSQL_HANDLER.get_unit(mssql_items)
    select = SelectBuilder(i.id_1, from_=i).where(i.id_1.is_in(list(range(2098))))

    assert len(select.to_sql().query_parameters) == 2098


def test_render_shows_an_oversized_statement_to_sql_would_reject():
    i = MSSQL_HANDLER.get_unit(mssql_items)
    select = SelectBuilder(i.id_1, from_=i).where(i.id_1.is_in(list(range(3000))))

    assert "SELECT" in select.render()


def test_sqlite_headroom_accepts_a_list_mssql_rejects():
    i = SQLITE_HANDLER.get_unit(items)
    select = SelectBuilder(i.id_1, from_=i).where(i.id_1.is_in(list(range(3000))))

    assert len(select.to_sql().query_parameters) == 3000
