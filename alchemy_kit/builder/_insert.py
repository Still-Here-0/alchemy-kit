from collections.abc import Sequence
from typing import Any, cast

import pandas as pd
import sqlalchemy as sa
from sqlalchemy.sql.expression import Insert

from ..model.units import ColumnUnit, ObjectUnit
from ..resources._pandas import none_if_na
from ..resources._sql import SQL
from ..resources.dialect_map import get_map
from ..types.sql_types import SqlScalarType
from ._base import SqlBuilder
from ._select import SelectBuilder
from ._utils import _Assignment


class InsertBuilder(SqlBuilder):
    """Builds an ``INSERT`` into an object unit's table; rows come from
    :meth:`from_values`, :meth:`from_dataframe` or :meth:`from_select`.

    These methods layer onto the statement rather than reset it: repeated
    :meth:`from_values` merge columns (last wins per column), repeated
    :meth:`from_dataframe` append rows, and repeated :meth:`from_select`
    replaces the prior SELECT. Mixing value sources (single vs multi VALUES,
    or values vs SELECT) raises ``InvalidRequestError``."""

    def __init__(self, target: ObjectUnit[Any]) -> None:
        super().__init__(target._base, target._handler)

        selectable = target._selectable
        if not isinstance(selectable, sa.Table):
            raise TypeError("insert target must be a plain object unit, not an aliased one")

        self._table = selectable
        self._stmt: Insert = sa.insert(selectable)

    def _with(self, stmt: Insert) -> "InsertBuilder":
        clone = InsertBuilder.__new__(InsertBuilder)
        SqlBuilder.__init__(clone, self._base, self._handler)
        clone._table = self._table
        clone._stmt = stmt
        return clone

    def _statement(self) -> Insert:
        return self._stmt

    def _sql_name(self, name: str) -> str:
        sql_name = getattr(self._base, name, name)
        return sql_name if isinstance(sql_name, str) else name

    def get_parameters(self) -> dict[str, SqlScalarType] | list[dict[str, SqlScalarType]]:
        """Return the values to insert, keyed by SQL column name: a dict for
        :meth:`from_values`, one dict per row for :meth:`from_dataframe`
        (empty for select inserts)."""
        if multi_values := self._stmt._multi_values:
            rows = cast("tuple[Sequence[dict[str, SqlScalarType]], ...]", multi_values)
            return [dict(row) for group in rows for row in group]

        if not (values := self._stmt._values):
            return {}

        return cast(
            "dict[str, SqlScalarType]",
            {getattr(column, "name", column): parameter.value for column, parameter in values.items()},
        )

    def from_values(
        self,
        assignment: _Assignment,
        *assignments: _Assignment,
    ) -> "InsertBuilder":
        """Set the inserted row's values as ``(column, value)`` pairs of units;
        a plain value is bound as a parameter and a value unit renders as an
        expression."""
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
            {target[name]: ColumnUnit._value_operand(none_if_na(record[name])) for name in source}
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
        if select._handler is not self._handler:
            raise ValueError("all units in a query must come from the same engine handler")
        stmt = select._statement()

        if columns is not None:
            names = [self._sql_name(name) for name in columns]
        else:
            names = list(stmt.selected_columns.keys())

        return self._with(self._stmt.from_select(names, stmt))

    def to_sqls(
        self,
        *,
        chunk_size: int | None = None,
        **parameters: Any,
    ) -> list[SQL]:
        """Compile the insert into one or more dialect-safe SQL statements.

        Multi-row inserts are split according to the dialect's row and
        parameter limits, further restricted by ``chunk_size`` when given.
        """
        rows = [row for group in self._stmt._multi_values for row in group]
        effective = self._effective_chunk_size(chunk_size, rows)

        if effective is None or len(rows) <= effective:
            return [super().to_sql(**parameters)]

        return [
            self._chunk_sql(rows[start:start + effective], parameters)
            for start in range(0, len(rows), effective)
        ]

    def run(self, *, chunk_size: int | None = None, **parameters: Any) -> tuple[int | None, pd.DataFrame]:
        """Execute the insert; a multi-row ``from_dataframe`` insert that would
        exceed the dialect's per-statement row/parameter limits (or
        ``chunk_size`` when given) is split into chunks run in one
        all-or-nothing transaction."""
        sqls = self.to_sqls(chunk_size=chunk_size, **parameters)

        if len(sqls) == 1:
            return self._handler.run_sql(sqls[0])

        counts = [count for count, _ in self._handler.run_sqls(sqls)]

        if any(count is None for count in counts):
            return None, pd.DataFrame()
        return sum(cast("list[int]", counts)), pd.DataFrame()

    def _effective_chunk_size(self, chunk_size: int | None, rows: Sequence[Any]) -> int | None:
        if not rows:
            return None

        limits = get_map(self._handler._con_info.dialect)
        caps: list[int] = []
        if limits.max_insert_rows is not None:
            caps.append(limits.max_insert_rows)
        if limits.max_statement_params is not None:
            caps.append(limits.max_statement_params // len(rows[0]))

        safe_max = min(caps) if caps else None

        if chunk_size is None:
            return safe_max
        if safe_max is None:
            return chunk_size
        return min(chunk_size, safe_max)

    def _chunk_sql(
        self,
        chunk: Sequence[Any],
        parameters: dict[str, Any],
    ) -> SQL:
        compiled = sa.insert(self._table).values(list(chunk)).compile(
            dialect=self._sa_dialect(),
            compile_kwargs={"render_postcompile": True},
        )
        return SQL(
            raw_query=str(compiled),
            query_parameters={**(compiled.params or {}), **parameters},
        )
