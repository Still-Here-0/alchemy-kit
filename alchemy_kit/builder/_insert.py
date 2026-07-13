from typing import Any, Sequence

import pandas as pd
import sqlalchemy as sa
from sqlalchemy.sql.expression import Insert

from ..model.units import ColumnUnit, ObjectUnit
from ._base import SqlBuilder
from ._select import SelectBuilder


class InsertBuilder(SqlBuilder):
    """Builds an ``INSERT`` into an object unit's table; rows come from
    :meth:`values`, :meth:`from_dataframe` or :meth:`from_select`."""

    def __init__(self, target: ObjectUnit[Any]) -> None:
        super().__init__(target._base)

        selectable = target._selectable
        if not isinstance(selectable, sa.Table):
            raise TypeError("insert target must be a plain object unit, not an aliased one")

        self._table = selectable
        self._stmt: Insert = sa.insert(selectable)

    def _with(self, stmt: Insert) -> "InsertBuilder":
        clone = InsertBuilder.__new__(InsertBuilder)
        SqlBuilder.__init__(clone, self._base)
        clone._table = self._table
        clone._stmt = stmt
        return clone

    def _statement(self) -> Insert:
        return self._stmt

    def _sql_name(self, name: str) -> str:
        sql_name = getattr(self._base, name, name)
        return sql_name if isinstance(sql_name, str) else name

    def values(self, **column_values: Any) -> "InsertBuilder":
        """Set the inserted row's values by model field (or SQL column)
        name; plain values are bound as parameters."""
        resolved = {
            self._sql_name(name): ColumnUnit._value_operand(value)
            for name, value in column_values.items()
        }
        return self._with(self._stmt.values(**resolved))

    def from_dataframe(
        self,
        df: pd.DataFrame,
        columns: Sequence[str] | None = None,
    ) -> "InsertBuilder":
        """Insert every row of ``df`` as one multi-row ``INSERT``;
        ``columns`` selects and orders which columns (all when omitted)."""
        source = list(df.columns) if columns is None else list(columns)
        target = {name: self._sql_name(name) for name in source}
        
        rows = [
            {target[name]: ColumnUnit._value_operand(record[name]) for name in source}
            for record in df.to_dict(orient="records")
        ]
        return self._with(self._stmt.values(rows))

    def from_select(
        self,
        select: SelectBuilder,
        columns: Sequence[str] | None = None,
    ) -> "InsertBuilder":
        """Insert the rows produced by a :class:`SelectBuilder`
        (``INSERT INTO ... SELECT``); ``columns`` names the targets in the
        select's output order (the select's own names when omitted)."""
        stmt = select._statement()

        if columns is not None:
            names = [self._sql_name(name) for name in columns]
        else:
            names = list(stmt.selected_columns.keys())

        return self._with(self._stmt.from_select(names, stmt))

