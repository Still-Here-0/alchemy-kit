from collections.abc import Sequence
from typing import Any, cast

import pandas as pd
import sqlalchemy as sa
from sqlalchemy.sql.expression import ClauseElement, Insert

from ..model.units import ColumnUnit, ObjectUnit
from ..resources._pandas import none_if_na
from ..resources._sql import SQL
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
        self._record_names: list[str] | None = None

    def _with(self, stmt: Insert, record_names: list[str] | None = None) -> "InsertBuilder":
        clone = InsertBuilder.__new__(InsertBuilder)
        SqlBuilder.__init__(clone, self._base, self._handler)
        clone._table = self._table
        clone._stmt = stmt
        clone._record_names = record_names if record_names is not None else self._record_names
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
        if (records := self._records({})) is not None:
            return cast("list[dict[str, SqlScalarType]]", records)

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
        """Insert every row of ``df`` as one bound record per row; ``columns``
        selects and orders which columns (all when omitted).

        The target column names are kept even when ``df`` holds no rows, so an
        empty frame still compiles to the statement it would have run.
        """
        source = list(df.columns) if columns is None else list(columns)
        target = {name: self._sql_name(name) for name in source}

        rows = [
            {target[name]: ColumnUnit._value_operand(none_if_na(record[name])) for name in source}
            for record in df.to_dict(orient="records")
        ]
        names = list(target.values())

        if not rows:
            return self._with(self._stmt, names)
        return self._with(self._stmt.values(rows), names)

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

    def returning(self, *columns: ColumnUnit[Any]) -> "InsertBuilder":
        """Return the inserted rows in the ``run`` DataFrame, as ``RETURNING``
        or MSSQL's ``OUTPUT inserted.*``; every column of the target when none
        are named. Raises on a dialect that cannot hand them back.

        A DataFrame insert then runs as the multi-row ``VALUES`` statements
        :meth:`to_sqls` compiles, since a statement executed once per bound
        record leaves the rows it returns unreachable."""
        return self._with(
            self._stmt.returning(*self._returned_columns("INSERT", self._table, columns))
        )

    def to_sql(self, **parameters: Any) -> SQL:
        """Compile the insert into a single :class:`SQL`.

        A multi-row insert compiles to a one-row ``INSERT`` template carrying
        every row as a bound record, executed once against the whole list. The
        statement binds one row's worth of parameters whatever the row count,
        so no dialect's per-statement parameter limit applies to it.
        """
        records = self._records(parameters)

        if records is None:
            return super().to_sql(**parameters)

        if records and self._returns_rows():
            raise ValueError(
                "a returning insert cannot bind one record per execution, which"
                " leaves the returned rows unreachable; compile it with to_sqls,"
                " or run it, which does that for you"
            )

        return self._checked(SQL(
            raw_query=self._record_template(records),
            query_parameters=records,
        ))

    def render(self) -> str:
        """Return the one-row ``INSERT`` template ``to_sql`` binds the records
        to, rather than the multi-row ``VALUES`` statement Core would compile.

        A :meth:`returning` insert of a DataFrame renders its first chunked
        statement instead, which is the form it runs as."""
        records = self._records({})

        if records is None:
            return super().render()

        if records and self._returns_rows():
            return cast("str", self.to_sqls()[0].raw_query)
        return self._record_template(records)

    def _rows(self) -> list[dict[str, Any]] | None:
        """Return one validated row per inserted row in a stable column order,
        or ``None`` when the statement is not a multi-row value insert and
        compiles on its own."""
        rows = cast(
            "list[dict[str, Any]]",
            [row for group in self._stmt._multi_values for row in group],
        )

        if not rows:
            return [] if self._record_names else None

        names = list(rows[0])
        self._check_bindable(rows[0])

        expected = rows[0].keys()
        for position, row in enumerate(rows):
            if row.keys() != expected:
                raise ValueError(
                    f"every inserted row must set the same columns; row {position}"
                    f" sets {sorted(row)} but the first sets {sorted(names)}"
                )

        return [{name: row[name] for name in names} for row in rows]

    def _records(self, parameters: dict[str, Any]) -> list[dict[str, Any]] | None:
        """Return one bound record per row, or ``None`` when the statement is
        not a multi-row value insert and compiles on its own."""
        rows = self._rows()

        if rows is None or not parameters:
            return rows
        return [row | parameters for row in rows]

    @staticmethod
    def _check_bindable(row: dict[str, Any]) -> None:
        for name, value in row.items():
            if isinstance(value, ClauseElement):
                raise TypeError(
                    f"column {name!r} is set to a SQL expression, which cannot be"
                    " bound as a value; insert expressions with from_values or"
                    " from_select instead"
                )

    def _record_template(self, records: Sequence[dict[str, Any]]) -> str:
        names = list(records[0]) if records else cast("list[str]", self._record_names)
        compiled = sa.insert(self._table).values(
            {name: sa.bindparam(name) for name in names}
        ).compile(dialect=self._sa_dialect())

        return str(compiled)

    def to_sqls(
        self,
        *,
        chunk_size: int | None = None,
        **parameters: Any,
    ) -> list[SQL]:
        """Compile the insert into multi-row ``INSERT ... VALUES`` statements,
        each carrying as many rows as the dialect's row cap and parameter budget
        allow, narrowed further by ``chunk_size``.

        Run the list through ``EngineHandler.run_sqls`` to keep the whole insert
        in one transaction. A dialect with no multi-row ``VALUES`` support
        raises; :meth:`to_sql` inserts any row count there.
        """
        rows = self._rows()

        if not rows:
            return [self.to_sql(**parameters)]

        if not self._sa_dialect().supports_multivalues_insert:
            raise ValueError(
                f"{self._handler.get_connection_info().dialect} cannot carry several rows in"
                " one VALUES clause; use to_sql, which binds every row to a"
                " single statement instead"
            )

        size = self._chunk_rows(chunk_size, rows)

        return [
            self._values_sql(rows[start:start + size], parameters)
            for start in range(0, len(rows), size)
        ]

    def _chunk_rows(self, chunk_size: int | None, rows: Sequence[dict[str, Any]]) -> int:
        """Rows one statement may carry: the dialect's row cap and parameter
        budget, narrowed by ``chunk_size``."""
        if chunk_size is not None and chunk_size < 1:
            raise ValueError(f"chunk_size must be at least 1, got {chunk_size}")

        limits = self._handler.get_connection_info().dialect.limits
        caps = [cap for cap in (chunk_size, limits.max_values_rows) if cap is not None]

        if columns := len(rows[0]):
            caps.append(limits.param_budget // columns)

        return max(1, min(caps, default=len(rows)))

    def _values_sql(self, chunk: Sequence[dict[str, Any]], parameters: dict[str, Any]) -> SQL:
        stmt = sa.insert(self._table).values(list(chunk))

        if returned := self._returning_clause():
            stmt = cast("Insert", stmt.returning(*returned))

        compiled = stmt.compile(
            dialect=self._sa_dialect(),
            compile_kwargs={"render_postcompile": True},
        )

        return self._checked(SQL(
            raw_query=str(compiled),
            query_parameters={**(compiled.params or {}), **parameters},
        ))

    def run(self, *, chunk_size: int | None = None, **parameters: Any) -> tuple[int | None, pd.DataFrame]:
        """Execute the insert, returning its ``(row_count, DataFrame)`` pair.

        Without ``chunk_size`` the insert runs as the one statement
        :meth:`to_sql` compiles, bound once per row; with it the rows are split
        into the multi-row statements :meth:`to_sqls` compiles, run in one
        all-or-nothing transaction. A :meth:`returning` insert of a DataFrame
        takes the chunked route whatever ``chunk_size`` says, and its rows come
        back as one frame.
        """
        if chunk_size is None and not (self._returns_rows() and self._rows()):
            return super().run(**parameters)

        sqls = self.to_sqls(chunk_size=chunk_size, **parameters)

        if len(sqls) == 1:
            return self._handler.run_sql(sqls[0])

        results = self._handler.run_sqls(sqls)
        counts = [count for count, _ in results]

        if any(count is None for count in counts):
            return None, pd.DataFrame()
        return sum(cast("list[int]", counts)), pd.concat(
            [data for _, data in results], ignore_index=True
        )
