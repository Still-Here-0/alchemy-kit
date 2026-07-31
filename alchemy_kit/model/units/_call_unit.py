from typing import TYPE_CHECKING, Any

import pandas as pd
import sqlalchemy as sa
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.elements import BindParameter
from sqlalchemy.sql.expression import ClauseElement

from ...resources._sql import SQL
from ...resources.dialect_map import get_sa_dialect
from ...types.dialect_types import DialectTypes
from ...types.sql_types import SqlScalarType
from ..callable_model import CallableModel

if TYPE_CHECKING:
    from ...connect._engine_handler import EngineHandler


class _Call(ClauseElement):
    inherit_cache = True

    def __init__(self, reference: str, bind_params: list[BindParameter[Any]]) -> None:
        self.reference = reference
        self.bind_params = bind_params


@compiles(_Call)
def _compile_call(element: _Call, compiler: Any, **kw: Any) -> str:
    args = ", ".join(compiler.process(param, **kw) for param in element.bind_params)
    return f"CALL {element.reference}({args})"


@compiles(_Call, DialectTypes.MSSQL)
def _compile_call_mssql(element: _Call, compiler: Any, **kw: Any) -> str:
    args = ", ".join(compiler.process(param, **kw) for param in element.bind_params)
    return f"EXEC {element.reference} {args}".rstrip()


@compiles(_Call, DialectTypes.SQLITE)
def _compile_call_sqlite(element: _Call, compiler: Any, **kw: Any) -> str:
    raise ValueError("SQLite does not support stored procedure calls")


class CallableUnit:
    """A stored procedure from a generated model, bound to a connection
    through ``handler``.

    :meth:`run` executes the procedure with the given arguments; :meth:`to_sql`
    and :meth:`render` produce the dialect-correct ``CALL``/``EXEC`` statement
    without running it."""

    def __init__(
        self,
        base: type[CallableModel],
        handler: "EngineHandler[Any]",
    ) -> None:
        self._base = base
        self._handler = handler

    def render(self, *args: SqlScalarType) -> str:
        """Return the SQL string exactly as ``run`` would execute it, with
        ``:name`` placeholders for bound values."""
        return str(self._compile(args))

    def to_sql(self, *args: SqlScalarType) -> SQL:
        """Compile into a :class:`SQL` for ``EngineHandler.run_sql``; plain
        values are bound as parameters."""
        compiled = self._compile(args)
        return SQL(
            raw_query=str(compiled),
            query_parameters=dict(compiled.params or {}),
        )

    def run(self, *args: SqlScalarType) -> tuple[int | None, pd.DataFrame]:
        """Compile and execute on the handler this unit came from, returning
        its ``(row_count, DataFrame)`` pair."""
        return self._handler.run_sql(self.to_sql(*args))

    def _element(self, args: tuple[SqlScalarType, ...]) -> _Call:
        reference = self._base.Config.metadata["reference_name"]
        bind_params = [sa.bindparam(f"p{index}", value) for index, value in enumerate(args)]
        return _Call(reference, bind_params)

    def _compile(self, args: tuple[SqlScalarType, ...]) -> sa.Compiled:
        dialect = get_sa_dialect(self._handler._con_info.dialect)
        return self._element(args).compile(
            dialect=dialect,
            compile_kwargs={"render_postcompile": True},
        )
