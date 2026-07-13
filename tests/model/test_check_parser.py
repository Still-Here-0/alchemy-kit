import pytest

from alchemy_kit.model._builders._check_parser import (
    ColumnComparisonCheck,
    IndexFilterCondition,
    parse_column_check,
    parse_index_filter,
    parse_table_check,
)
from alchemy_kit.types.dialect_types import DialectTypes


@pytest.mark.parametrize(
    ("definition", "dialect", "column", "expected"),
    [
        ("([price]>(0.00))", DialectTypes.MSSQL, "price", {"gt": 0.0}),
        ("([price]>=(-5))", DialectTypes.MSSQL, "price", {"ge": -5}),
        ("((0)<[price])", DialectTypes.MSSQL, "price", {"gt": 0}),
        ("([status] IN ('open','closed'))", DialectTypes.MSSQL, "status", {"isin": ["open", "closed"]}),
        ("([qty] BETWEEN (1) AND (100))", DialectTypes.MSSQL, "qty", {"ge": 1, "le": 100}),
        ("([a]>=(0) AND [a]<=(10))", DialectTypes.MSSQL, "a", {"ge": 0, "le": 10}),
        ("age >= 18", DialectTypes.SQLITE, "age", {"ge": 18}),
        ('(("state")=(2))', DialectTypes.POSTGRESQL, "state", {"eq": 2}),
    ],
)
def test_parse_column_check_supported(definition, dialect, column, expected):
    assert parse_column_check(definition, dialect, column) == expected


@pytest.mark.parametrize(
    ("definition", "dialect", "column"),
    [
        ("(len([code])=(8))", DialectTypes.MSSQL, "code"),
        ("([a]>(0) OR [a]<(-10))", DialectTypes.MSSQL, "a"),
        ("([other]>(0))", DialectTypes.MSSQL, "price"),
        ("([a]>(0) AND [a]>(10))", DialectTypes.MSSQL, "a"),
        ("([name] LIKE 'A%')", DialectTypes.MSSQL, "name"),
        ("garbage ((", DialectTypes.MSSQL, "a"),
    ],
)
def test_parse_column_check_unsupported(definition, dialect, column):
    assert parse_column_check(definition, dialect, column) is None


def test_parse_table_check_comparison():
    assert parse_table_check("([start_date]<=[end_date])", DialectTypes.MSSQL) == ColumnComparisonCheck(
        "start_date", "<=", "end_date"
    )
    assert parse_table_check("start_date <= end_date", DialectTypes.SQLITE) == ColumnComparisonCheck(
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
    assert parse_table_check(definition, DialectTypes.MSSQL) is None


@pytest.mark.parametrize(
    ("definition", "dialect", "expected"),
    [
        ("([code] IS NOT NULL)", DialectTypes.MSSQL, [("code", "is_not_null", None)]),
        ("([a] IS NOT NULL AND [b] IS NOT NULL)", DialectTypes.MSSQL, [("a", "is_not_null", None), ("b", "is_not_null", None)]),
        ("code IS NOT NULL", DialectTypes.SQLITE, [("code", "is_not_null", None)]),
        ("([active]=(1))", DialectTypes.MSSQL, [("active", "==", 1)]),
        ("([status]=('open'))", DialectTypes.MSSQL, [("status", "==", "open")]),
        ("((1)=[active])", DialectTypes.MSSQL, [("active", "==", 1)]),
        ("([type]<>('archived'))", DialectTypes.MSSQL, [("type", "!=", "archived")]),
        ("([code] IS NOT NULL AND [active]=(1))", DialectTypes.MSSQL, [("code", "is_not_null", None), ("active", "==", 1)]),
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
    assert parse_index_filter(definition, DialectTypes.MSSQL) is None
