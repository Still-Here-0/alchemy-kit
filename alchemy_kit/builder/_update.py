from typing import Any

import sqlalchemy as sa
from sqlalchemy.sql.expression import Update

from ..model.units import BooleanColumnUnit, ColumnUnit, ObjectUnit
from ..types.sql_types import SqlScalarType
from ._base import SqlBuilder

type _Assignment = tuple[ColumnUnit[Any], ColumnUnit[Any] | SqlScalarType]


class UpdateBuilder(SqlBuilder):
    """Builds an ``UPDATE`` of an object unit's table: :meth:`set_values`
    assigns the new column values and :meth:`where` restricts the rows they
    apply to.

    Each may be used once per builder, and the values must be set before the
    statement compiles. Without a :meth:`where` the update rewrites every row
    of the table."""

    def __init__(self, target: ObjectUnit[Any]) -> None:
        super().__init__(target._base, target._handler)

        selectable = target._selectable
        if not isinstance(selectable, sa.Table):
            raise TypeError("update target must be a plain object unit, not an aliased one")

        self._table = selectable
        self._stmt: Update = sa.update(selectable)

    def _with(self, stmt: Update) -> "UpdateBuilder":
        clone = UpdateBuilder.__new__(UpdateBuilder)
        SqlBuilder.__init__(clone, self._base, self._handler)
        clone._table = self._table
        clone._stmt = stmt
        return clone

    def _statement(self) -> Update:
        return self._stmt

    def set_values(
        self,
        assignment: _Assignment,
        *assignments: _Assignment,
    ) -> "UpdateBuilder":
        """Assign new values as ``(column, value)`` pairs of units; a plain
        value is bound as a parameter and a value unit is evaluated per row, so
        ``(unit.price, unit.price * 2)`` renders as an expression."""
        pairs = (assignment, *assignments)
        self._check_units(
            *(unit for pair in pairs for unit in pair if isinstance(unit, ColumnUnit))
        )
        return self._with(
            self._stmt.values({
                column._element: ColumnUnit._value_operand(value)
                for column, value in pairs
            })
        )

    def where(self, *conditions: BooleanColumnUnit[Any]) -> "UpdateBuilder":
        """Restrict the updated rows (multiple conditions are ``AND``-ed)."""
        self._check_units(*conditions)
        return self._with(self._stmt.where(*(c._element for c in conditions)))
