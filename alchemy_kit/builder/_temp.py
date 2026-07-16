from typing import Any

import sqlalchemy as sa
from sqlalchemy.schema import CreateTable

from ..model._table import clone_table
from ..model.units import ObjectUnit
from ..types.dialect_types import DialectTypes
from ._base import SqlBuilder


class TempBuilder(SqlBuilder):
    """Builds the dialect-correct ``CREATE TABLE`` for a temporary table
    named ``TEMP_<source>``, cloning an object unit's columns.

    ``global_temp`` makes it visible to other sessions where the dialect
    supports that (``##`` on MSSQL, inherent on Oracle, error elsewhere).
    """

    def __init__(self, source: ObjectUnit[Any], global_temp: bool = False) -> None:
        super().__init__(source._base, source._handler)

        table = source._selectable
        if not isinstance(table, sa.Table):
            raise TypeError("temp source must be a plain object unit, not an aliased one")

        dialect = self._handler._con_info.dialect
        temp_name = f"TEMP_{table.name}"
        prefixes: list[str] = ["TEMPORARY"]

        if dialect is DialectTypes.MSSQL:
            temp_name = f"{'##' if global_temp else '#'}{temp_name}"
            prefixes = []
        elif dialect is DialectTypes.ORACLE:
            prefixes = ["GLOBAL TEMPORARY"]
        elif global_temp:
            raise ValueError(
                f"{dialect} does not support global temporary tables"
            )

        self._table = clone_table(table, temp_name, prefixes)

    def _statement(self) -> CreateTable:
        return CreateTable(self._table)

    def unit(self) -> ObjectUnit[Any]:
        """Return an :class:`ObjectUnit` over the temporary table, for
        selecting from / inserting into it after :meth:`run`."""
        return ObjectUnit(self._base, self._handler, self._table)

