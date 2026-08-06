from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd
import sqlalchemy as sa
from sqlalchemy import Compiled
from sqlalchemy.engine import Dialect
from sqlalchemy.sql.expression import ClauseElement, ColumnElement

from ..connect._engine_handler import EngineHandler
from ..model.base_model import BaseModel
from ..model.units._column_unit import ColumnUnit, _ExpressionUnit
from ..model.units._object_unit import ObjectUnit
from ..resources._sql import SQL
from ..types.errors import StatementLimitError
from ..types.returning_support import ReturningStatement


class SqlBuilder(ABC):
    """Base of every SQL statement builder: assembles a SQLAlchemy Core
    statement from units and compiles it against the dialect of the engine
    handler the units came from. Subclasses implement ``_statement``;
    builders are immutable."""

    def __init__(self, base: type[BaseModel], handler: EngineHandler[Any]) -> None:
        self._base = base
        self._handler = handler

    def _check_units(self, *units: "_ExpressionUnit[Any] | ObjectUnit[Any]") -> None:
        for unit in units:
            if unit._handler is not None and unit._handler is not self._handler:
                raise ValueError("all units in a query must come from the same engine handler")

    @abstractmethod
    def _statement(self) -> ClauseElement:
        """Return the Core statement this builder currently describes."""

    def _returned_columns(
        self,
        statement: ReturningStatement,
        table: sa.Table,
        columns: Sequence[ColumnUnit[Any]],
    ) -> list[ColumnElement[Any]]:
        """Return the columns a returning clause should carry — every column of
        ``table`` when none are named — once the dialect can read them back."""
        dialect = self._handler.get_connection_info().dialect

        if not dialect.returning.allows(statement):
            raise ValueError(
                f"{dialect.name} cannot return the rows {statement} affects;"
                " read them back with a separate SELECT"
            )

        self._check_units(*columns)

        if not columns:
            return list(table.columns)
        return [column._element for column in columns]

    def _returning_clause(self) -> tuple[ColumnElement[Any], ...]:
        """Return the columns the statement's returning clause carries, empty
        when it has none."""
        return getattr(self._statement(), "_returning", ())

    def _returns_rows(self) -> bool:
        """Whether the statement carries a returning clause."""
        return bool(self._returning_clause())

    def _sa_dialect(self) -> Dialect:
        return self._handler.get_connection_info().dialect.sa_dialect()

    def _compile(self) -> Compiled:
        return self._statement().compile(
            dialect=self._sa_dialect(),
            compile_kwargs={"render_postcompile": True},
        )

    def to_sql(self, **parameters: Any) -> SQL:
        """Compile into a :class:`SQL` for ``EngineHandler.run_sql``; keyword
        arguments supply or override bound parameters."""
        compiled = self._compile()

        return self._checked(SQL(
            raw_query=str(compiled),
            query_parameters={**(compiled.params or {}), **parameters},
        ))

    def _checked(self, sql: SQL) -> SQL:
        """Return ``sql`` once its statement fits the dialect's parameter
        budget, raising :class:`StatementLimitError` when it does not."""
        dialect = self._handler.get_connection_info().dialect
        budget = dialect.limits.param_budget
        needed = len(sql.parameter_names())

        if needed <= budget:
            return sql

        if isinstance(sql.query_parameters, Mapping):
            remedy = (
                "bind fewer values — a long value list is better staged into a"
                " temporary table with TempBuilder and joined"
            )
        else:
            remedy = (
                "the target binds more columns than the dialect allows in one"
                " statement; write fewer columns at a time"
            )

        raise StatementLimitError(dialect.name, needed, budget, remedy)

    def render(self) -> str:
        """Return the compiled SQL string with ``:name`` placeholders for bound
        values, for inspection; it does not check the dialect's parameter
        budget the way ``to_sql`` does."""
        return str(self._compile())

    def run(self, **parameters: Any) -> tuple[int | None, pd.DataFrame]:
        """Compile and execute on the engine handler the units came from,
        returning its ``(row_count, DataFrame)`` pair."""
        sql = self.to_sql(**parameters)
        return self._handler.run_sql(sql)
