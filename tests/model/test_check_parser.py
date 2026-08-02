import pytest

from alchemy_kit.model._builders._check_parser import (
    ColumnComparisonCheck,
    IndexFilterCondition,
    parse_column_check,
    parse_index_filter,
    parse_table_check,
)
from alchemy_kit.resources.dialect_map import DialectMap, MssqlMap, PostgresqlMap, SqliteMap


@pytest.mark.parametrize(
    ("definition", "dialect", "column", "expected"),
    [
        ("([price]>(0.00))", MssqlMap, "price", {"gt": 0.0}),
        ("([price]>=(-5))", MssqlMap, "price", {"ge": -5}),
        ("((0)<[price])", MssqlMap, "price", {"gt": 0}),
        ("([status] IN ('open','closed'))", MssqlMap, "status", {"isin": ["open", "closed"]}),
        ("([qty] BETWEEN (1) AND (100))", MssqlMap, "qty", {"ge": 1, "le": 100}),
        ("([a]>=(0) AND [a]<=(10))", MssqlMap, "a", {"ge": 0, "le": 10}),
        ("age >= 18", SqliteMap, "age", {"ge": 18}),
        ('(("state")=(2))', PostgresqlMap, "state", {"eq": 2}),
    ],
)
def test_parse_column_check_supported(definition, dialect, column, expected):
    assert parse_column_check(definition, dialect, column) == expected


@pytest.mark.parametrize(
    ("definition", "dialect", "column"),
    [
        ("(len([code])=(8))", MssqlMap, "code"),
        ("([a]>(0) OR [a]<(-10))", MssqlMap, "a"),
        ("([other]>(0))", MssqlMap, "price"),
        ("([a]>(0) AND [a]>(10))", MssqlMap, "a"),
        ("([name] LIKE 'A%')", MssqlMap, "name"),
        ("garbage ((", MssqlMap, "a"),
    ],
)
def test_parse_column_check_unsupported(definition, dialect, column):
    assert parse_column_check(definition, dialect, column) is None


def test_parse_table_check_comparison():
    assert parse_table_check("([start_date]<=[end_date])", MssqlMap) == ColumnComparisonCheck(
        "start_date", "<=", "end_date"
    )
    assert parse_table_check("start_date <= end_date", SqliteMap) == ColumnComparisonCheck(
        "start_date", "<=", "end_date"
    )


@pytest.mark.parametrize(
    "definition",
    [
        "([price]>(0))",
        "([a]<=[b] AND [b]<=[c])",
        "garbage ((",
    ],
)
def test_parse_table_check_unsupported(definition):
    assert parse_table_check(definition, MssqlMap) is None


@pytest.mark.parametrize(
    ("definition", "dialect", "expected"),
    [
        ("([code] IS NOT NULL)", MssqlMap, [("code", "is_not_null", None)]),
        ("([a] IS NOT NULL AND [b] IS NOT NULL)", MssqlMap, [("a", "is_not_null", None), ("b", "is_not_null", None)]),
        ("code IS NOT NULL", SqliteMap, [("code", "is_not_null", None)]),
        ("([active]=(1))", MssqlMap, [("active", "==", 1)]),
        ("([status]=('open'))", MssqlMap, [("status", "==", "open")]),
        ("((1)=[active])", MssqlMap, [("active", "==", 1)]),
        ("([type]<>('archived'))", MssqlMap, [("type", "!=", "archived")]),
        ("([code] IS NOT NULL AND [active]=(1))", MssqlMap, [("code", "is_not_null", None), ("active", "==", 1)]),
    ],
)
def test_parse_index_filter_supported(definition, dialect, expected):
    assert parse_index_filter(definition, dialect) == [IndexFilterCondition(*item) for item in expected]


@pytest.mark.parametrize(
    "definition",
    [
        "([code] IS NULL)",
        "([a] IS NOT NULL OR [b] IS NOT NULL)",
        "([qty]>(0))",
        "([a]=[b])",
        "(upper([status])=('OPEN'))",
        "garbage ((",
    ],
)
def test_parse_index_filter_unsupported(definition):
    assert parse_index_filter(definition, MssqlMap) is None
