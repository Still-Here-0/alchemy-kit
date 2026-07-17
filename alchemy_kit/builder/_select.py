from typing import Any

import sqlalchemy as sa
from sqlalchemy.sql.expression import ColumnElement, FromClause, Join, Select

from ..model.units import BooleanColumnUnit, ColumnUnit, ObjectUnit, OrderingColumnUnit
from ..types.sql_types import SqlJoinTypes
from ._base import SqlBuilder

_JOIN_FLAGS: dict[SqlJoinTypes, dict[str, bool]] = {
    "INNER": {},
    "LEFT": {"isouter": True},
    "FULL": {"isouter": True, "full": True},
}


class SelectBuilder(SqlBuilder):
    """Builds a ``SELECT`` statement over ``table`` (the ``FROM`` clause);
    when no columns are given every column of ``table`` is selected. The
    dialect comes from the table's engine handler and every fluent method
    returns a new builder."""

    def __init__(
        self,
        from_: ObjectUnit[Any],
        *columns: "ColumnUnit[Any] | ObjectUnit[Any]",
    ) -> None:
        super().__init__(from_._base, from_._handler)
        self._check_units(from_, *columns)
        selected = columns if columns else (from_,)
        self._stmt: Select[Any] = sa.select(*(self._selected(c) for c in selected))
        self._from: FromClause = from_._selectable

    @staticmethod
    def _selected(column: "ColumnUnit[Any] | ObjectUnit[Any]") -> Any:
        if isinstance(column, ObjectUnit):
            return column._selectable
        return column._element

    @staticmethod
    def _condition_element(condition: BooleanColumnUnit[Any]) -> ColumnElement[bool]:
        return condition._element

    @staticmethod
    def _column_element(column: ColumnUnit[Any]) -> ColumnElement[Any]:
        return column._element

    @staticmethod
    def _ordering_element(
        column: "ColumnUnit[Any] | OrderingColumnUnit[Any]",
    ) -> ColumnElement[Any]:
        return column._element

    @staticmethod
    def _required_condition(
        how: SqlJoinTypes, on: "BooleanColumnUnit[Any] | None"
    ) -> ColumnElement[bool]:
        if on is None:
            raise TypeError(f"{how} join requires an on condition")
        return SelectBuilder._condition_element(on)

    def _with(
        self, stmt: Select[Any], joined: FromClause | None = None
    ) -> "SelectBuilder":
        clone = SelectBuilder.__new__(SelectBuilder)
        SqlBuilder.__init__(clone, self._base, self._handler)
        clone._stmt = stmt
        clone._from = joined if joined is not None else self._from
        return clone

    def _statement(self) -> Select[Any]:
        return self._stmt.select_from(self._from)

    def as_scalar(self) -> "ColumnUnit[Any]":
        """Return this select as a scalar subquery value unit, usable in a
        select list, comparison or other value context; the select must
        produce a single column. Outer columns referenced in ``where`` make
        it a correlated subquery."""
        return ColumnUnit(
            self._statement().scalar_subquery(), self._base, self._handler
        )

    def as_object(self, name: str) -> "ObjectUnit[Any]":
        """Return this select as a named derived table usable as a ``FROM``
        source or join target; its columns are reached by the source models'
        field names, same as any object unit."""
        return ObjectUnit(
            self._base, self._handler, self._statement().subquery(name)
        )

    def where(self, *conditions: BooleanColumnUnit[Any]) -> "SelectBuilder":
        """Add ``WHERE`` conditions (multiple conditions are ``AND``-ed)."""
        self._check_units(*conditions)
        return self._with(
            self._stmt.where(*(self._condition_element(c) for c in conditions))
        )

    def join(
        self,
        how: SqlJoinTypes,
        other: ObjectUnit[Any],
        on: BooleanColumnUnit[Any] | None = None,
    ) -> "SelectBuilder":
        """Add a join to ``other``; ``CROSS`` takes no ``on`` condition and
        ``RIGHT`` compiles as the equivalent operand-flipped ``LEFT OUTER
        JOIN``."""
        self._check_units(*(other,) if on is None else (other, on))
        left = self._from

        joined: Join
        match how:
            case "CROSS":
                if on is not None:
                    raise TypeError("CROSS join takes no on condition")
                joined = sa.join(left, other._selectable, sa.true())
            case "RIGHT":
                joined = sa.outerjoin(
                    other._selectable, left, self._required_condition(how, on)
                )
            case _:
                joined = sa.join(
                    left,
                    other._selectable,
                    self._required_condition(how, on),
                    **_JOIN_FLAGS[how],
                )

        return self._with(self._stmt, joined)

    def group_by(self, *columns: ColumnUnit[Any]) -> "SelectBuilder":
        """Add ``GROUP BY`` expressions."""
        self._check_units(*columns)
        return self._with(
            self._stmt.group_by(*(self._column_element(c) for c in columns))
        )

    def having(self, *conditions: BooleanColumnUnit[Any]) -> "SelectBuilder":
        """Add ``HAVING`` conditions (multiple conditions are ``AND``-ed)."""
        self._check_units(*conditions)
        return self._with(
            self._stmt.having(*(self._condition_element(c) for c in conditions))
        )

    def order_by(
        self, *columns: "ColumnUnit[Any] | OrderingColumnUnit[Any]"
    ) -> "SelectBuilder":
        """Add ``ORDER BY`` expressions (direction via the column's
        ``asc()``/``desc()``)."""
        self._check_units(*columns)
        return self._with(
            self._stmt.order_by(*(self._ordering_element(c) for c in columns))
        )

    def distinct(self) -> "SelectBuilder":
        """Deduplicate the result rows (``SELECT DISTINCT``)."""
        return self._with(self._stmt.distinct())

    def limit(self, count: int) -> "SelectBuilder":
        """Cap the number of returned rows; the dialect decides the rendering
        (``TOP``/``LIMIT``/``FETCH NEXT``)."""
        return self._with(self._stmt.limit(count))

    def offset(self, count: int) -> "SelectBuilder":
        """Skip the first ``count`` rows (usually paired with ``limit`` and
        an ``order_by``)."""
        return self._with(self._stmt.offset(count))

