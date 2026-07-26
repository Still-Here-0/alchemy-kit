from typing import Any

import pandas as pd
import sqlalchemy as sa
from sqlalchemy.schema import CreateTable

from ..connect._engine_handler import EngineHandler
from ..model.base_model import BaseModel
from ..model._builders._column_metadata import ColumnMetadata
from ..model.units import ObjectUnit
from ..types.dialect_types import DialectTypes
from ..types.temp_table_types import TempTableType
from ._base import SqlBuilder
from ._utils import DataFrameTemp, sa_type_from_series


class TempBuilder(SqlBuilder):
    """Builds the dialect-correct ``CREATE TABLE`` for a temporary table
    named ``TEMP_<source>``, cloning an object unit's columns.

    The staging type controls whether database-defaulted columns are retained;
    identity and computed columns are omitted from the staging variants but
    kept by ``FULL``.
    ``global_temp`` makes it visible to other sessions where the dialect
    supports that (``##`` on MSSQL, inherent on Oracle, error elsewhere).
    """

    def __init__(
        self,
        source: ObjectUnit[Any],
        global_temp: bool = False,
        stage: TempTableType = TempTableType.STAGE,
    ) -> None:
        table = source._selectable
        if not isinstance(table, sa.Table):
            raise TypeError("temp source must be a plain object unit, not an aliased one")

        generated = self._database_generated_columns(source._base, stage)
        columns = [
            sa.Column(
                c.name,
                c.type,
                nullable=c.nullable,
                primary_key=c.primary_key and stage is TempTableType.FULL,
            )
            for c in table.columns
            if c.name not in generated
        ]
        self._configure(source._base, source._handler, table.name, columns, global_temp)

    @staticmethod
    def _database_generated_columns(
        base: type[BaseModel[Any]],
        table_type: TempTableType,
    ) -> set[str]:
        if table_type is TempTableType.FULL:
            return set()

        return {
            str(name)
            for name, column in base.to_schema().columns.items()
            if (metadata := ColumnMetadata.from_dict(column.metadata)).identity
            or metadata.computed
            or (metadata.has_default and table_type is TempTableType.STAGE)
        }

    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        handler: EngineHandler,
        name: str,
        *,
        base: type[BaseModel[Any]] | None = None,
        global_temp: bool = False,
    ) -> "TempBuilder":
        """Build a ``TempBuilder`` whose column schema is inferred from ``df``'s
        dtypes, for a temp table named ``TEMP_<name>``.

        The DataFrame's column names become the SQL column names; pass ``base``
        to resolve them through a generated model's field names instead.
        """
        self = cls.__new__(cls)
        if df.columns.has_duplicates:
            duplicates = df.columns[df.columns.duplicated()].unique().tolist()
            raise ValueError(f"DataFrame has duplicate column names: {duplicates}")

        columns = [sa.Column(str(c), sa_type_from_series(df[c])) for c in df.columns]
        self._configure(base or DataFrameTemp, handler, name, columns, global_temp)
        return self

    def _configure(
        self,
        base: type[BaseModel[Any]],
        handler: EngineHandler,
        source_name: str,
        columns: list[sa.Column[Any]],
        global_temp: bool,
    ) -> None:
        SqlBuilder.__init__(self, base, handler)

        dialect = handler._con_info.dialect
        temp_name = f"TEMP_{source_name}"
        prefixes: list[str] = ["TEMPORARY"]

        if dialect is DialectTypes.MSSQL:
            temp_name = f"{'##' if global_temp else '#'}{temp_name}"
            prefixes = []
        elif dialect is DialectTypes.ORACLE:
            prefixes = ["GLOBAL TEMPORARY"]
        elif global_temp:
            raise ValueError(f"{dialect} does not support global temporary tables")

        self._table = sa.Table(temp_name, sa.MetaData(), *columns, prefixes=prefixes)

    def _statement(self) -> CreateTable:
        return CreateTable(self._table)

    def unit(self) -> ObjectUnit[Any]:
        """Return an :class:`ObjectUnit` over the temporary table, for
        selecting from / inserting into it after :meth:`run`."""
        return ObjectUnit(self._base, self._handler, self._table)
