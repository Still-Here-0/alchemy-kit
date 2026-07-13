from collections.abc import Iterable
from datetime import date, datetime
from typing import Any, Self

import sqlalchemy as sa
from sqlalchemy.sql.expression import ColumnElement

from ..base_model import BaseModel

type _Value = int | float | str | bytes | date | datetime | None
type _Operand = ColumnUnit[Any] | _Value
type _Condition = BooleanColumnUnit[Any] | bool


class _ExpressionUnit[_TypeParameters: str]:
    """Immutable wrapper around a SQLAlchemy Core column expression, bound to
    the model's dialect through ``base``. Every operation on a unit returns a
    new unit."""

    __hash__ = object.__hash__

    def __init__(
        self,
        element: ColumnElement[Any],
        base: type[BaseModel[_TypeParameters]],
    ) -> None:
        self._element = element
        self._base    = base
        self._map     = base._map

    def set_alias(self, alias: str) -> Self:
        """Return a new unit with the output name for this expression set."""
        return type(self)(self._element.label(alias), self._base)

    @staticmethod
    def _operand(value: Any) -> Any:
        return value._element if isinstance(value, _ExpressionUnit) else value

    def __bool__(self) -> bool:
        raise TypeError(
            "A column expression has no truth value; combine conditions with"
            " '&', '|' and '~' instead of 'and', 'or' and 'not'"
        )


class ColumnUnit[_TypeParameters: str](_ExpressionUnit[_TypeParameters]):
    """A value column expression from a model, generic over the dialect's SQL
    type names (``_TypeParameters``, inferred from ``base``).

    Arithmetic (``+``, ``-``, ``*``, ``/``) composes new :class:`ColumnUnit`
    instances, and comparisons (``==``, ``!=``, ``<``, ``<=``, ``>``, ``>=``)
    produce :class:`BooleanColumnUnit` conditions. Operands may be other value
    units or plain Python values, which are bound as parameters by Core;
    conditions are not values and are rejected as operands.
    """

    def cast(self, to: _TypeParameters) -> "ColumnUnit[_TypeParameters]":
        """Return a new unit casting this column to a SQL type of the model's
        dialect."""
        return self._unit(sa.cast(self._element, self._map.get_sa_type(to)))

    def sum(self) -> "ColumnUnit[_TypeParameters]":
        """Return a new unit aggregating this expression with ``SUM``."""
        return self._unit(sa.func.sum(self._element))

    def avg(self) -> "ColumnUnit[_TypeParameters]":
        """Return a new unit aggregating this expression with ``AVG``."""
        return self._unit(sa.func.avg(self._element))

    def min(self) -> "ColumnUnit[_TypeParameters]":
        """Return a new unit aggregating this expression with ``MIN``."""
        return self._unit(sa.func.min(self._element))

    def max(self) -> "ColumnUnit[_TypeParameters]":
        """Return a new unit aggregating this expression with ``MAX``."""
        return self._unit(sa.func.max(self._element))

    def count(self, distinct: bool = False) -> "ColumnUnit[_TypeParameters]":
        """Return a new unit aggregating this expression with ``COUNT``
        (``COUNT(DISTINCT ...)`` when ``distinct`` is set)."""
        element = sa.distinct(self._element) if distinct else self._element
        return self._unit(sa.func.count(element))

    def distinct(self) -> "ColumnUnit[_TypeParameters]":
        """Return a new unit wrapping this expression with ``DISTINCT``."""
        return self._unit(sa.distinct(self._element))

    def coalesce(self, *fallbacks: _Operand) -> "ColumnUnit[_TypeParameters]":
        """Return a new unit rendering ``COALESCE(<this>, <fallbacks>...)`` —
        the first non-null value in order."""
        return self._unit(
            sa.func.coalesce(self._element, *(self._value_operand(f) for f in fallbacks))
        )

    def abs(self) -> "ColumnUnit[_TypeParameters]":
        """Return a new unit rendering ``ABS(<this>)``."""
        return self._unit(sa.func.abs(self._element))

    def round(self, digits: int = 0) -> "ColumnUnit[_TypeParameters]":
        """Return a new unit rendering ``ROUND(<this>, digits)``."""
        return self._unit(sa.func.round(self._element, digits))

    def apply(self, function: str, *args: _Operand) -> "ColumnUnit[_TypeParameters]":
        """Return a new unit applying an arbitrary SQL function to this
        expression, e.g. ``apply("upper")`` or ``apply("power", 2)``. The
        function name is rendered as-is; extra arguments may be value units or
        plain Python values, which are bound as parameters by Core."""
        return self._unit(
            getattr(sa.func, function)(
                self._element, *(self._value_operand(a) for a in args)
            )
        )

    def asc(self) -> "ColumnUnit[_TypeParameters]":
        """Return a new unit ordering by this expression ascending."""
        return self._unit(self._element.asc())

    def desc(self) -> "ColumnUnit[_TypeParameters]":
        """Return a new unit ordering by this expression descending."""
        return self._unit(self._element.desc())

    def nulls_first(self) -> "ColumnUnit[_TypeParameters]":
        """Return a new unit placing nulls first when this expression is used
        for ordering (chain after :meth:`asc`/:meth:`desc`)."""
        return self._unit(self._element.nulls_first())

    def nulls_last(self) -> "ColumnUnit[_TypeParameters]":
        """Return a new unit placing nulls last when this expression is used
        for ordering (chain after :meth:`asc`/:meth:`desc`)."""
        return self._unit(self._element.nulls_last())

    def is_in(self, values: Iterable[_Operand]) -> "BooleanColumnUnit[_TypeParameters]":
        """Return a condition rendering ``<this> IN (<values>...)``."""
        return self._condition(
            self._element.in_([self._value_operand(v) for v in values])
        )

    def not_in(self, values: Iterable[_Operand]) -> "BooleanColumnUnit[_TypeParameters]":
        """Return a condition rendering ``<this> NOT IN (<values>...)``."""
        return self._condition(
            self._element.not_in([self._value_operand(v) for v in values])
        )

    def is_null(self) -> "BooleanColumnUnit[_TypeParameters]":
        """Return a condition rendering ``<this> IS NULL``."""
        return self._condition(self._element.is_(None))

    def is_not_null(self) -> "BooleanColumnUnit[_TypeParameters]":
        """Return a condition rendering ``<this> IS NOT NULL``."""
        return self._condition(self._element.is_not(None))

    def between(self, low: _Operand, high: _Operand) -> "BooleanColumnUnit[_TypeParameters]":
        """Return a condition rendering ``<this> BETWEEN low AND high``
        (inclusive on both ends)."""
        return self._condition(
            self._element.between(self._value_operand(low), self._value_operand(high))
        )

    def like(self, pattern: _Operand, escape: str | None = None) -> "BooleanColumnUnit[_TypeParameters]":
        """Return a condition rendering ``<this> LIKE pattern`` (``%`` and
        ``_`` wildcards; ``escape`` sets the escape character)."""
        return self._condition(self._element.like(self._value_operand(pattern), escape=escape))

    def ilike(self, pattern: _Operand, escape: str | None = None) -> "BooleanColumnUnit[_TypeParameters]":
        """Return a condition matching ``pattern`` case-insensitively
        (``ILIKE`` where the dialect has it, ``lower() LIKE lower()``
        elsewhere)."""
        return self._condition(self._element.ilike(self._value_operand(pattern), escape=escape))

    def starts_with(self, prefix: _Operand) -> "BooleanColumnUnit[_TypeParameters]":
        """Return a condition matching values that start with ``prefix``
        (``LIKE 'prefix%'``, with wildcards in ``prefix`` escaped)."""
        return self._condition(self._element.startswith(self._value_operand(prefix), autoescape=True))

    def ends_with(self, suffix: _Operand) -> "BooleanColumnUnit[_TypeParameters]":
        """Return a condition matching values that end with ``suffix``
        (``LIKE '%suffix'``, with wildcards in ``suffix`` escaped)."""
        return self._condition(self._element.endswith(self._value_operand(suffix), autoescape=True))

    def contains(self, infix: _Operand) -> "BooleanColumnUnit[_TypeParameters]":
        """Return a condition matching values that contain ``infix``
        (``LIKE '%infix%'``, with wildcards in ``infix`` escaped)."""
        return self._condition(self._element.contains(self._value_operand(infix), autoescape=True))

    def _unit(self, element: ColumnElement[Any]) -> "ColumnUnit[_TypeParameters]":
        return ColumnUnit(element, self._base)

    def _condition(self, element: ColumnElement[bool]) -> "BooleanColumnUnit[_TypeParameters]":
        return BooleanColumnUnit(element, self._base)

    @staticmethod
    def _value_operand(value: Any) -> Any:
        if isinstance(value, BooleanColumnUnit):
            raise TypeError(
                "A boolean condition is not a value; it cannot be used in"
                " arithmetic or compared to a column"
            )
        return _ExpressionUnit._operand(value)

    def __add__(self, other: _Operand) -> "ColumnUnit[_TypeParameters]":
        return self._unit(self._element + self._value_operand(other))

    def __radd__(self, other: _Operand) -> "ColumnUnit[_TypeParameters]":
        return self._unit(self._value_operand(other) + self._element)

    def __sub__(self, other: _Operand) -> "ColumnUnit[_TypeParameters]":
        return self._unit(self._element - self._value_operand(other))

    def __rsub__(self, other: _Operand) -> "ColumnUnit[_TypeParameters]":
        return self._unit(self._value_operand(other) - self._element)

    def __mul__(self, other: _Operand) -> "ColumnUnit[_TypeParameters]":
        return self._unit(self._element * self._value_operand(other))

    def __rmul__(self, other: _Operand) -> "ColumnUnit[_TypeParameters]":
        return self._unit(self._value_operand(other) * self._element)

    def __truediv__(self, other: _Operand) -> "ColumnUnit[_TypeParameters]":
        return self._unit(self._element / self._value_operand(other))

    def __rtruediv__(self, other: _Operand) -> "ColumnUnit[_TypeParameters]":
        return self._unit(self._value_operand(other) / self._element)

    def __mod__(self, other: _Operand) -> "ColumnUnit[_TypeParameters]":
        return self._unit(self._element % self._value_operand(other))

    def __rmod__(self, other: _Operand) -> "ColumnUnit[_TypeParameters]":
        return self._unit(self._value_operand(other) % self._element)

    def __neg__(self) -> "ColumnUnit[_TypeParameters]":
        return self._unit(-self._element)

    def __eq__(self, other: _Operand) -> "BooleanColumnUnit[_TypeParameters]":  # pyright: ignore[reportIncompatibleMethodOverride]
        return self._condition(self._element == self._value_operand(other))

    def __ne__(self, other: _Operand) -> "BooleanColumnUnit[_TypeParameters]":  # pyright: ignore[reportIncompatibleMethodOverride]
        return self._condition(self._element != self._value_operand(other))

    def __lt__(self, other: _Operand) -> "BooleanColumnUnit[_TypeParameters]":
        return self._condition(self._element < self._value_operand(other))

    def __le__(self, other: _Operand) -> "BooleanColumnUnit[_TypeParameters]":
        return self._condition(self._element <= self._value_operand(other))

    def __gt__(self, other: _Operand) -> "BooleanColumnUnit[_TypeParameters]":
        return self._condition(self._element > self._value_operand(other))

    def __ge__(self, other: _Operand) -> "BooleanColumnUnit[_TypeParameters]":
        return self._condition(self._element >= self._value_operand(other))


class BooleanColumnUnit[_TypeParameters: str](_ExpressionUnit[_TypeParameters]):
    """A boolean condition (comparison result or combination thereof) that
    composes only with other conditions through ``&`` (AND), ``|`` (OR) and
    ``~`` (NOT). It is not a value column: arithmetic and comparisons are not
    available on it, and it is rejected as an operand of a :class:`ColumnUnit`.
    """

    _element: ColumnElement[bool]

    def in_case(
        self,
        then: _Operand,
        *elifs: "tuple[BooleanColumnUnit[Any], _Operand]",
        otherwise: _Operand = None,
    ) -> "ColumnUnit[_TypeParameters]":
        """Return a value unit rendering a ``CASE`` expression — the portable
        way to use a condition as a value (e.g. conditional aggregation).

        This condition and ``then`` form the first ``WHEN``; each extra
        ``(condition, value)`` pair in ``elifs`` appends another ``WHEN``,
        evaluated in order like Python's ``elif``. ``otherwise`` is the
        ``ELSE``; omitting it leaves the SQL default ``ELSE NULL``. Values may
        be value units or plain Python values, which are bound as parameters
        by Core.
        """
        whens = [(self._element, ColumnUnit._value_operand(then))]

        for branch in elifs:
            if not (isinstance(branch, tuple) and len(branch) == 2):
                raise TypeError(
                    "each extra CASE branch must be a (condition, value)"
                    f" tuple, got {branch!r}"
                )
            condition, value = branch
            if not isinstance(condition, BooleanColumnUnit):
                raise TypeError(
                    "a CASE branch condition must be a boolean condition, got"
                    f" {type(condition).__name__}"
                )
            whens.append((condition._element, ColumnUnit._value_operand(value)))

        return ColumnUnit(
            sa.case(*whens, else_=ColumnUnit._value_operand(otherwise)),
            self._base,
        )

    def _condition(self, element: ColumnElement[bool]) -> "BooleanColumnUnit[_TypeParameters]":
        return BooleanColumnUnit(element, self._base)

    @staticmethod
    def _condition_operand(value: Any) -> Any:
        if not isinstance(value, (BooleanColumnUnit, bool)):
            raise TypeError(
                "A condition combines only with other conditions or bool, got"
                f" {type(value).__name__}"
            )
        return _ExpressionUnit._operand(value)

    def __and__(self, other: _Condition) -> "BooleanColumnUnit[_TypeParameters]":
        return self._condition(sa.and_(self._element, self._condition_operand(other)))

    def __rand__(self, other: _Condition) -> "BooleanColumnUnit[_TypeParameters]":
        return self._condition(sa.and_(self._condition_operand(other), self._element))

    def __or__(self, other: _Condition) -> "BooleanColumnUnit[_TypeParameters]":
        return self._condition(sa.or_(self._element, self._condition_operand(other)))

    def __ror__(self, other: _Condition) -> "BooleanColumnUnit[_TypeParameters]":
        return self._condition(sa.or_(self._condition_operand(other), self._element))

    def __invert__(self) -> "BooleanColumnUnit[_TypeParameters]":
        return self._condition(sa.not_(self._element))

