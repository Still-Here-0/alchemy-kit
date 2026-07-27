from typing import Any

import sqlalchemy as sa
from sqlalchemy.sql.expression import Delete

from ..model.units import BooleanColumnUnit, ObjectUnit
from ._base import SqlBuilder
from ._utils import plain_table


class DeleteBuilder(SqlBuilder):
    """Builds a ``DELETE`` from an object unit's table; :meth:`where`
    restricts the removed rows and may be used once per builder. Without a
    :meth:`where` the delete removes every row of the table."""

    def __init__(self, target: ObjectUnit[Any]) -> None:
        super().__init__(target._base, target._handler)
        self._table = plain_table(target, "delete")
        self._stmt: Delete = sa.delete(self._table)

    def _with(self, stmt: Delete) -> "DeleteBuilder":
        clone = DeleteBuilder.__new__(DeleteBuilder)
        SqlBuilder.__init__(clone, self._base, self._handler)
        clone._table = self._table
        clone._stmt = stmt
        return clone

    def _statement(self) -> Delete:
        return self._stmt

    def where(self, *conditions: BooleanColumnUnit[Any]) -> "DeleteBuilder":
        """Restrict the deleted rows (multiple conditions are ``AND``-ed)."""
        self._check_units(*conditions)
        return self._with(self._stmt.where(*(c._element for c in conditions)))
