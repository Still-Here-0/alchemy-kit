from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

import pandas as pd
from sqlalchemy import Compiled
from sqlalchemy.engine import Dialect
from sqlalchemy.sql.expression import ClauseElement

from ..connect._engine_handler import EngineHandler
from ..model.base_model import BaseModel
from ..model.units._column_unit import _ExpressionUnit
from ..model.units._object_unit import ObjectUnit
from ..resources._sql import SQL
from ..resources.dialect_map import get_map, get_sa_dialect
from ..types.errors import StatementLimitError


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

    def _sa_dialect(self) -> Dialect:
        return get_sa_dialect(self._handler._con_info.dialect)

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
        dialect = self._handler._con_info.dialect
        budget = get_map(dialect).limits.param_budget
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

        raise StatementLimitError(dialect, needed, budget, remedy)

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
