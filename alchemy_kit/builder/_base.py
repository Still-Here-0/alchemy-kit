from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import pandas as pd
from sqlalchemy import Compiled
from sqlalchemy.engine import Dialect
from sqlalchemy.sql.expression import ClauseElement

from ..model.base_model import BaseModel
from ..model.units._column_unit import _ExpressionUnit
from ..model.units._object_unit import ObjectUnit
from ..resources._sql import SQL
from ..resources.dialect_map import get_sa_dialect

if TYPE_CHECKING:
    from ..connect._engine_handler import EngineHandler


class SqlBuilder(ABC):
    """Base of every SQL statement builder: assembles a SQLAlchemy Core
    statement from units and compiles it against the dialect of the engine
    handler the units came from. Subclasses implement ``_statement``;
    builders are immutable."""

    def __init__(self, base: type[BaseModel[Any]], handler: "EngineHandler") -> None:
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

        return SQL(
            raw_query=str(compiled),
            query_parameters={**(compiled.params or {}), **parameters},
        )

    def render(self) -> str:
        """Return the SQL string exactly as ``run`` would execute it, with
        ``:name`` placeholders for bound values."""
        return str(self._compile())

    def run(self, **parameters: Any) -> tuple[int | None, pd.DataFrame]:
        """Compile and execute on the engine handler the units came from,
        returning its ``(row_count, DataFrame)`` pair."""
        sql = self.to_sql(**parameters)
        return self._handler.run_sql(sql)
