from typing import Any

import sqlalchemy as sa
from sqlalchemy.schema import CreateTable

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
        super().__init__(source._base)

        table = source._selectable
        if not isinstance(table, sa.Table):
            raise TypeError("temp source must be a plain object unit, not an aliased one")

        temp_name = f"TEMP_{table.name}"
        prefixes: list[str] = ["TEMPORARY"]

        if self._base._dialect is DialectTypes.MSSQL:
            temp_name = f"{'##' if global_temp else '#'}{temp_name}"
            prefixes = []
        elif self._base._dialect is DialectTypes.ORACLE:
            prefixes = ["GLOBAL TEMPORARY"]
        elif global_temp:
            raise ValueError(
                f"{self._base._dialect} does not support global temporary tables"
            )

        self._table = sa.Table(
            temp_name,
            sa.MetaData(),
            *(
                sa.Column(c.name, c.type, nullable=c.nullable, primary_key=c.primary_key)
                for c in table.columns
            ),
            prefixes=prefixes,
        )

    def _statement(self) -> CreateTable:
        return CreateTable(self._table)

    def unit(self) -> ObjectUnit[Any]:
        """Return an :class:`ObjectUnit` over the temporary table, for
        selecting from / inserting into it after :meth:`run`."""
        return ObjectUnit(self._base, self._table)

