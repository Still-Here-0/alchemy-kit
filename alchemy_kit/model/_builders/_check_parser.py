from decimal import Decimal
from typing import Any, NamedTuple

import sqlglot
from sqlglot import expressions as exp
from sqlglot.errors import SqlglotError

from ...types.dialect_types import DialectTypes

_SQLGLOT_DIALECTS: dict[DialectTypes, str] = {
    DialectTypes.MSSQL: "tsql",
    DialectTypes.MYSQL: "mysql",
    DialectTypes.MARIADB: "mysql",
    DialectTypes.POSTGRESQL: "postgres",
    DialectTypes.SQLITE: "sqlite",
    DialectTypes.ORACLE: "oracle",
}

_COMPARISON_FIELD_ARGS: dict[type[exp.Expr], str] = {
    exp.GT: "gt",
    exp.GTE: "ge",
    exp.LT: "lt",
    exp.LTE: "le",
    exp.EQ: "eq",
    exp.NEQ: "ne",
}

_FLIPPED_FIELD_ARGS: dict[str, str] = {
    "gt": "lt",
    "ge": "le",
    "lt": "gt",
    "le": "ge",
    "eq": "eq",
    "ne": "ne",
}

_COMPARISON_PY_OPERATORS: dict[type[exp.Expr], str] = {
    exp.GT: ">",
    exp.GTE: ">=",
    exp.LT: "<",
    exp.LTE: "<=",
    exp.EQ: "==",
    exp.NEQ: "!=",
}


class ColumnComparisonCheck(NamedTuple):
    """A table-level CHECK comparing two columns, e.g. ``start_date <= end_date``."""

    left_column: str
    py_operator: str
    right_column: str


def parse_column_check(definition: str, dialect: DialectTypes, column_name: str) -> dict[str, Any] | None:
    """Translate a single-column CHECK definition into ``pandera.Field``
    keyword arguments (``gt``/``ge``/``lt``/``le``/``eq``/``ne``/``isin``).

    Supports literal comparisons in either direction, ``IN`` lists,
    ``BETWEEN``, and ``AND`` conjunctions of those. Returns ``None`` for any
    shape outside that set (function calls, casts, ``OR``, ``LIKE``, ...) so
    the caller can fall back to recording the raw definition.
    """
    node = _parse(definition, dialect)
    if node is None:
        return None

    return _field_args(node, column_name)


def parse_table_check(definition: str, dialect: DialectTypes) -> ColumnComparisonCheck | None:
    """Translate a table-level CHECK into a two-column comparison, returning
    ``None`` for any other shape."""
    node = _parse(definition, dialect)
    if node is None or type(node) not in _COMPARISON_PY_OPERATORS:
        return None

    left = node.this.unnest() if isinstance(node.this, exp.Expr) else None
    right = node.expression.unnest() if isinstance(node.expression, exp.Expr) else None

    if not isinstance(left, exp.Column) or not isinstance(right, exp.Column):
        return None

    return ColumnComparisonCheck(left.name, _COMPARISON_PY_OPERATORS[type(node)], right.name)


class IndexFilterCondition(NamedTuple):
    """One condition of a filtered-index WHERE clause.

    ``operator`` is ``"is_not_null"`` (``value`` is ``None``), ``"=="`` or
    ``"!="`` (``value`` holds the compared literal).
    """

    column: str
    operator: str
    value: Any | None


_FILTER_OPERATORS: dict[type[exp.Expr], str] = {
    exp.EQ: "==",
    exp.NEQ: "!=",
}


def parse_index_filter(definition: str, dialect: DialectTypes) -> list[IndexFilterCondition] | None:
    """Translate a filtered-index WHERE clause into mask conditions.

    Supports ``<col> IS NOT NULL``, ``<col> = <literal>``, ``<col> <> <literal>``
    and ``AND`` conjunctions of those; returns ``None`` for any other shape so
    the caller can fall back to recording the raw definition.
    """
    node = _parse(definition, dialect)
    if node is None:
        return None

    return _filter_conditions(node)


def _filter_conditions(node: exp.Expr) -> list[IndexFilterCondition] | None:
    if isinstance(node, exp.And):
        left = _filter_conditions(node.this.unnest())
        right = _filter_conditions(node.expression.unnest())
        if left is None or right is None:
            return None
        return left + right

    if isinstance(node, exp.Not):
        return _not_null_condition(node)

    operator = _FILTER_OPERATORS.get(type(node))
    if operator is None:
        return None

    left = node.this.unnest()
    right = node.expression.unnest()

    if isinstance(left, exp.Column):
        value = _literal_value(right)
        return None if value is None else [IndexFilterCondition(left.name, operator, value)]

    if isinstance(right, exp.Column):
        value = _literal_value(left)
        return None if value is None else [IndexFilterCondition(right.name, operator, value)]

    return None


def _not_null_condition(node: exp.Not) -> list[IndexFilterCondition] | None:
    inner = node.this
    if not isinstance(inner, exp.Expr):
        return None

    inner = inner.unnest()
    if not isinstance(inner, exp.Is):
        return None

    column = inner.this.unnest() if isinstance(inner.this, exp.Expr) else None
    value = inner.expression.unnest() if isinstance(inner.expression, exp.Expr) else None

    if not isinstance(column, exp.Column) or not isinstance(value, exp.Null):
        return None

    return [IndexFilterCondition(column.name, "is_not_null", None)]


def _parse(definition: str, dialect: DialectTypes) -> exp.Expr | None:
    try:
        parsed = sqlglot.parse_one(definition, read=_SQLGLOT_DIALECTS[dialect])
    except SqlglotError:
        return None

    return parsed.unnest()


def _field_args(node: exp.Expr, column_name: str) -> dict[str, Any] | None:
    if isinstance(node, exp.And):
        return _merge_args(
            _field_args(node.this.unnest(), column_name),
            _field_args(node.expression.unnest(), column_name),
        )

    if isinstance(node, exp.Between):
        if not _is_expected_column(node.this, column_name):
            return None

        low = _literal_value(node.args.get("low"))
        high = _literal_value(node.args.get("high"))
        if low is None or high is None:
            return None

        return {"ge": low, "le": high}

    if isinstance(node, exp.In):
        if not _is_expected_column(node.this, column_name) or node.args.get("query"):
            return None

        values = [_literal_value(item) for item in node.expressions]
        if any(value is None for value in values):
            return None

        return {"isin": values}

    arg_name = _COMPARISON_FIELD_ARGS.get(type(node))
    if arg_name is None:
        return None

    left = node.this.unnest()
    right = node.expression.unnest()

    if _is_expected_column(left, column_name):
        value = _literal_value(right)
        return None if value is None else {arg_name: value}

    if _is_expected_column(right, column_name):
        value = _literal_value(left)
        return None if value is None else {_FLIPPED_FIELD_ARGS[arg_name]: value}

    return None


def _merge_args(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any] | None:
    if left is None or right is None or left.keys() & right.keys():
        return None

    return {**left, **right}


def _is_expected_column(node: exp.Expr | None, column_name: str) -> bool:
    if not isinstance(node, exp.Expr):
        return False

    unnested = node.unnest()
    return isinstance(unnested, exp.Column) and unnested.name.lower() == column_name.lower()


def _literal_value(node: exp.Expr | None) -> Any | None:
    if not isinstance(node, exp.Expr):
        return None

    unnested = node.unnest()

    negative = isinstance(unnested, exp.Neg)
    if negative:
        inner = unnested.this
        if not isinstance(inner, exp.Expr):
            return None
        unnested = inner.unnest()

    if not isinstance(unnested, exp.Literal):
        return None

    value = unnested.to_py()
    if isinstance(value, Decimal):
        value = float(value)

    if not negative:
        return value

    return -value if isinstance(value, (int, float)) else None
