from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import pandas as pd
from sqlalchemy import Compiled
from sqlalchemy.engine import Dialect
from sqlalchemy.sql.expression import ClauseElement

from ..model.base_model import BaseModel
from ..resources._sql import SQL
from ..resources.dialect_map import get_sa_dialect

if TYPE_CHECKING:
    from ..connect._engine_handler import EngineHandler


class SqlBuilder(ABC):
    """Base of every SQL statement builder: assembles a SQLAlchemy Core
    statement from units and compiles it against the model's dialect.
    Subclasses implement ``_statement``; builders are immutable."""

    def __init__(self, base: type[BaseModel[Any]]) -> None:
        self._base = base

    @abstractmethod
    def _statement(self) -> ClauseElement:
        """Return the Core statement this builder currently describes."""

    def _sa_dialect(self) -> Dialect:
        return get_sa_dialect(self._base._dialect)

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

    def run(self, handler: "EngineHandler", **parameters: Any) -> tuple[int | None, pd.DataFrame]:
        """Compile and execute through ``handler.run_sql``, returning its
        ``(row_count, DataFrame)`` pair."""
        return handler.run_sql(self.to_sql(**parameters))
