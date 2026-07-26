from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import ClauseElement

from ..model.units import ObjectUnit
from ..types.dialect_types import DialectTypes
from ._base import SqlBuilder
from ._utils import plain_table


class _Truncate(ClauseElement):
    inherit_cache = True

    def __init__(self, table: sa.Table) -> None:
        self.table = table


@compiles(_Truncate)
def _compile_truncate(element: _Truncate, compiler: Any, **_: Any) -> str:
    return f"TRUNCATE TABLE {compiler.preparer.format_table(element.table)}"


@compiles(_Truncate, DialectTypes.SQLITE)
def _compile_truncate_sqlite(element: _Truncate, compiler: Any, **_: Any) -> str:
    return f"DELETE FROM {compiler.preparer.format_table(element.table)}"


class TruncateBuilder(SqlBuilder):
    """Builds a ``TRUNCATE TABLE`` of an object unit's table (rendered as
    ``DELETE FROM`` on SQLite, which has no ``TRUNCATE``)."""

    def __init__(self, target: ObjectUnit[Any]) -> None:
        super().__init__(target._base, target._handler)
        self._table = plain_table(target, "truncate")
        self._stmt = _Truncate(self._table)

    def _statement(self) -> _Truncate:
        return self._stmt
