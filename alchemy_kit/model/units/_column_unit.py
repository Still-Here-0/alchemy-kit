from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy.sql.expression import ColumnElement
from sqlalchemy.sql.functions import Function

from ...resources.dialect_map import get_map
from ...types.sql_types import SqlScalarType
from ..base_model import BaseModel

if TYPE_CHECKING:
    from ...connect._engine_handler import EngineHandler

type _Operand = ColumnUnit[Any] | SqlScalarType
type _Condition = BooleanColumnUnit[Any] | bool
type _Sortable = ColumnUnit[Any] | OrderingColumnUnit[Any]


class _ExpressionUnit[_TypeParameters: str]:
    """Immutable wrapper around a SQLAlchemy Core column expression, bound to
    the connection's dialect through ``handler``. Every operation on a unit
    returns a new unit."""

    __hash__ = object.__hash__

    def __init__(
        self,
        element: ColumnElement[Any],
        base: type[BaseModel[_TypeParameters]] | None = None,
        handler: "EngineHandler | None" = None,
    ) -> None:
        self._element = element
        self._base    = base
        self._handler = handler

    @staticmethod
    def _operand(value: Any) -> Any:
        return value._element if isinstance(value, _ExpressionUnit) else value

    def __bool__(self) -> bool:
        raise TypeError(
            "A column expression has no truth value; combine conditions with"
            " '&', '|' and '~' instead of 'and', 'or' and 'not'"
        )


class _WindowMixin[_TypeParameters: str]:
    """Adds ``over`` to units wrapping SQL functions that accept an ``OVER``
    clause."""

    _element: Function[Any]
    _base: type[BaseModel[_TypeParameters]]
    _handler: "EngineHandler | None"

    def over(
        self,
        *,
        partition_by: "ColumnUnit[Any] | Iterable[ColumnUnit[Any]] | None" = None,
        order_by: "_Sortable | Iterable[_Sortable] | None" = None,
        rows: tuple[int | None, int | None] | None = None,
    ) -> "ColumnUnit[_TypeParameters]":
        """Return a value unit rendering ``<this> OVER (...)`` — the windowed
        form of the function, computed per row without collapsing rows.

        ``partition_by`` splits the rows into windows and ``order_by`` sorts
        within each; with ``order_by`` set, aggregates become cumulative.
        ``rows`` bounds the frame relative to the current row, e.g.
        ``(-6, 0)`` for the previous six rows through this one (``None`` in a
        bound means unbounded). The result is a plain value unit, but SQL
        accepts window expressions only in the select list and ``ORDER BY``,
        not in ``WHERE``, ``GROUP BY`` or ``HAVING``.

        ``OVER`` attaches to the function itself, so call this before any
        further operation — arithmetic or :meth:`ColumnUnit.set_alias` on an
        aggregate returns a plain :class:`ColumnUnit` that is no longer
        windowable; window first, alias last.
        """
        return ColumnUnit(
            self._element.over(
                partition_by=self._window_elements(partition_by),
                order_by=self._window_elements(order_by),
                rows=rows,
            ),
            self._base,
            self._handler,
        )

    @staticmethod
    def _window_elements(value: Any) -> list[ColumnElement[Any]] | None:
        if value is None:
            return None
        if isinstance(value, _ExpressionUnit):
            return [value._element]
        return [unit._element for unit in value]


class ColumnUnit[_TypeParameters: str](_ExpressionUnit[_TypeParameters]):
    """A value column expression from a model, generic over the dialect's SQL
    type names (``_TypeParameters``, inferred from ``base``).

    Arithmetic (``+``, ``-``, ``*``, ``/``, ``//``, ``%``) composes new
    :class:`ColumnUnit` instances, comparisons (``==``, ``!=``, ``<``, ``<=``,
    ``>``, ``>=``) produce :class:`BooleanColumnUnit` conditions, and
    ``asc()``/``desc()`` produce :class:`OrderingColumnUnit` expressions.
    Operands may be other value units or plain Python values, which are bound
    as parameters by Core; conditions are not values and are rejected as
    operands.
    """

    def set_alias(self, alias: str) -> "ColumnUnit[_TypeParameters]":
        """Return a new unit with the output name for this expression set."""
        return self._unit(self._element.label(alias))

    def cast(self, to: _TypeParameters) -> "ColumnUnit[_TypeParameters]":
        """Return a new unit casting this column to a SQL type of the
        connection's dialect."""
        assert self._handler is not None, "Cast requires a model-bound unit, this may be a bug. Report it on github."
        dialect_map = get_map(self._handler._con_info.dialect)
        return self._unit(sa.cast(self._element, dialect_map.get_sa_type(to)))

    def sum(self) -> "AggregateColumnUnit[_TypeParameters]":
        """Return a new unit aggregating this expression with ``SUM``."""
        return self._aggregate(sa.func.sum(self._element))

    def avg(self) -> "AggregateColumnUnit[_TypeParameters]":
        """Return a new unit aggregating this expression with ``AVG``."""
        return self._aggregate(sa.func.avg(self._element))

    def min(self) -> "AggregateColumnUnit[_TypeParameters]":
        """Return a new unit aggregating this expression with ``MIN``."""
        return self._aggregate(sa.func.min(self._element))

    def max(self) -> "AggregateColumnUnit[_TypeParameters]":
        """Return a new unit aggregating this expression with ``MAX``."""
        return self._aggregate(sa.func.max(self._element))

    def count(self, distinct: bool = False) -> "AggregateColumnUnit[_TypeParameters]":
        """Return a new unit aggregating this expression with ``COUNT``
        (``COUNT(DISTINCT ...)`` when ``distinct`` is set)."""
        element = sa.distinct(self._element) if distinct else self._element
        return self._aggregate(sa.func.count(element))

    def distinct(self) -> "ColumnUnit[_TypeParameters]":
        """Return a new unit wrapping this expression with ``DISTINCT``."""
        return self._unit(sa.distinct(self._element))

    def coalesce(self, *fallbacks: _Operand) -> "ColumnUnit[_TypeParameters]":
        """Return a new unit rendering ``COALESCE(<this>, <fallbacks>...)`` —
        the first non-null value in order."""
        return self._unit(
            sa.func.coalesce(self._element, *(self._value_operand(f) for f in fallbacks))
        )

    def nullif(self, value: _Operand) -> "ColumnUnit[_TypeParameters]":
        """Return a new unit rendering ``NULLIF(<this>, value)`` — null when
        this expression equals ``value``, e.g. ``total / count.nullif(0)``."""
        return self._unit(sa.func.nullif(self._element, self._value_operand(value)))

    def abs(self) -> "ColumnUnit[_TypeParameters]":
        """Return a new unit rendering ``ABS(<this>)``."""
        return self._unit(sa.func.abs(self._element))

    def round(self, digits: int = 0) -> "ColumnUnit[_TypeParameters]":
        """Return a new unit rendering ``ROUND(<this>, digits)``."""
        return self._unit(sa.func.round(self._element, digits))

    def lower(self) -> "ColumnUnit[_TypeParameters]":
        """Return a new unit rendering ``LOWER(<this>)``."""
        return self._unit(sa.func.lower(self._element))

    def upper(self) -> "ColumnUnit[_TypeParameters]":
        """Return a new unit rendering ``UPPER(<this>)``."""
        return self._unit(sa.func.upper(self._element))

    def length(self) -> "ColumnUnit[_TypeParameters]":
        """Return a new unit counting this expression's characters (the
        dialect's function: ``CHAR_LENGTH``/``LENGTH``/``LEN``)."""
        return self._unit(sa.func.char_length(self._element))

    def trim(self) -> "ColumnUnit[_TypeParameters]":
        """Return a new unit rendering ``TRIM(<this>)`` — leading and trailing
        whitespace removed."""
        return self._unit(sa.func.trim(self._element))

    def concat(self, *others: _Operand) -> "ColumnUnit[_TypeParameters]":
        """Return a new unit concatenating this expression with ``others`` in
        order, using the dialect's string concatenation operator."""
        element = self._element
        for other in others:
            element = element.concat(self._value_operand(other))
        return self._unit(element)

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

    def lag(self, offset: int = 1, default: _Operand = None) -> "WindowFunctionUnit[_TypeParameters]":
        """Return a window function rendering ``LAG(<this>, offset)`` — this
        expression's value from an earlier row of the window (needs ``over``,
        typically with ``order_by``). ``default`` replaces the null produced
        while no earlier row exists."""
        return self._window_function(sa.func.lag, offset, default)

    def lead(self, offset: int = 1, default: _Operand = None) -> "WindowFunctionUnit[_TypeParameters]":
        """Return a window function rendering ``LEAD(<this>, offset)`` — this
        expression's value from a later row of the window (needs ``over``,
        typically with ``order_by``). ``default`` replaces the null produced
        while no later row exists."""
        return self._window_function(sa.func.lead, offset, default)

    def asc(self) -> "OrderingColumnUnit[_TypeParameters]":
        """Return an ordering expression sorting by this expression
        ascending."""
        return OrderingColumnUnit(self._element.asc(), self._base, self._handler)

    def desc(self) -> "OrderingColumnUnit[_TypeParameters]":
        """Return an ordering expression sorting by this expression
        descending."""
        return OrderingColumnUnit(self._element.desc(), self._base, self._handler)

    def is_in(self, values: Iterable[_Operand], parse_null: bool = True) -> "BooleanColumnUnit[_TypeParameters]":
        """Return a condition rendering ``<this> IN (<values>...)``.

        A ``None`` among ``values`` never matches inside ``IN`` (comparing
        with null yields unknown), so it is lifted out into ``... OR <this>
        IS NULL``; pass ``parse_null=False`` to bind the null raw instead.
        """
        others = list(values)
        if parse_null and any(v is None for v in others):
            others = [v for v in others if v is not None]
            if not others:
                return self.is_null()
            return self.is_in(others) | self.is_null()

        return self._condition(
            self._element.in_([self._value_operand(v) for v in others])
        )

    def not_in(self, values: Iterable[_Operand], parse_null: bool = True) -> "BooleanColumnUnit[_TypeParameters]":
        """Return a condition rendering ``<this> NOT IN (<values>...)``.

        A ``None`` among ``values`` makes ``NOT IN`` match no rows at all
        (comparing with null yields unknown), so it is lifted out into
        ``... AND <this> IS NOT NULL``; pass ``parse_null=False`` to bind the
        null raw instead.
        """
        others = list(values)
        if parse_null and any(v is None for v in others):
            others = [v for v in others if v is not None]
            if not others:
                return self.is_not_null()
            return self.not_in(others) & self.is_not_null()

        return self._condition(
            self._element.not_in([self._value_operand(v) for v in others])
        )

    def is_null(self) -> "BooleanColumnUnit[_TypeParameters]":
        """Return a condition rendering ``<this> IS NULL``."""
        return self._condition(self._element.is_(None))

    def is_not_null(self) -> "BooleanColumnUnit[_TypeParameters]":
        """Return a condition rendering ``<this> IS NOT NULL``."""
        return self._condition(self._element.is_not(None))

    def is_distinct_from(self, other: _Operand) -> "BooleanColumnUnit[_TypeParameters]":
        """Return a condition true when the values differ, treating null as a
        comparable value (the null-safe ``!=``): ``1 IS DISTINCT FROM NULL``
        is true and ``NULL IS DISTINCT FROM NULL`` is false."""
        return self._condition(
            self._element.is_distinct_from(self._value_operand(other))
        )

    def is_not_distinct_from(self, other: _Operand) -> "BooleanColumnUnit[_TypeParameters]":
        """Return a condition true when the values match, treating null as a
        comparable value (the null-safe ``==``): ``NULL IS NOT DISTINCT FROM
        NULL`` is true."""
        return self._condition(
            self._element.is_not_distinct_from(self._value_operand(other))
        )

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
        return ColumnUnit(element, self._base, self._handler)

    def _condition(self, element: ColumnElement[bool]) -> "BooleanColumnUnit[_TypeParameters]":
        return BooleanColumnUnit(element, self._base, self._handler)

    def _aggregate(self, element: Function[Any]) -> "AggregateColumnUnit[_TypeParameters]":
        return AggregateColumnUnit(element, self._base, self._handler)

    def _window_function(
        self, function: Any, offset: int, default: _Operand
    ) -> "WindowFunctionUnit[_TypeParameters]":
        args = [self._element, offset]
        if default is not None:
            args.append(self._value_operand(default))
        return WindowFunctionUnit(function(*args), self._base, self._handler)

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

    def __floordiv__(self, other: _Operand) -> "ColumnUnit[_TypeParameters]":
        return self._unit(self._element // self._value_operand(other))

    def __rfloordiv__(self, other: _Operand) -> "ColumnUnit[_TypeParameters]":
        return self._unit(self._value_operand(other) // self._element)

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


class AggregateColumnUnit[_TypeParameters: str](ColumnUnit[_TypeParameters], _WindowMixin[_TypeParameters]):
    """An aggregated value column (:meth:`ColumnUnit.sum` and other methods
    from :class:`ColumnUnit`). It is a full value unit that can additionally
    be windowed with :meth:`over`.
    """


class OrderingColumnUnit[_TypeParameters: str](_ExpressionUnit[_TypeParameters]):
    """An ``ORDER BY`` expression (:meth:`ColumnUnit.asc`/``desc``, optionally
    refined with :meth:`nulls_first`/:meth:`nulls_last`). It is not a value
    column: arithmetic, comparisons and aggregation are not available on it,
    and only ordering clauses accept it.
    """

    def nulls_first(self) -> "OrderingColumnUnit[_TypeParameters]":
        """Return a new ordering expression placing nulls before all other
        values."""
        return OrderingColumnUnit(self._element.nulls_first(), self._base, self._handler)

    def nulls_last(self) -> "OrderingColumnUnit[_TypeParameters]":
        """Return a new ordering expression placing nulls after all other
        values."""
        return OrderingColumnUnit(self._element.nulls_last(), self._base, self._handler)


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
            self._handler,
        )

    def _condition(self, element: ColumnElement[bool]) -> "BooleanColumnUnit[_TypeParameters]":
        return BooleanColumnUnit(element, self._base, self._handler)

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


class WindowFunctionUnit[_TypeParameters: str](_ExpressionUnit[_TypeParameters], _WindowMixin[_TypeParameters]):
    """A window-only function (:meth:`ColumnUnit.lag`/``lead``,
    :meth:`ObjectUnit.row_number` and other methods from :class:`ObjectUnit`), 
    which is invalid SQL until :meth:`over` attaches its window; no other 
    operation is available.
    """

