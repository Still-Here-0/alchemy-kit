from collections.abc import Sequence
from typing import Any

import pandas as pd
from sqlalchemy.sql.expression import Insert

from ..model.units import ObjectUnit
from ..resources._sql import SQL
from ..types.sql_types import SqlScalarType
from ..types.typestate import Set, Unset
from ._base import SqlBuilder
from ._select import SelectBuilder

# F -> from_values() / from_dataframe() / from_select()
class InsertBuilder[F](SqlBuilder):
    def __new__(cls, target: ObjectUnit[Any]) -> InsertBuilder[Unset]: ...
    def __init__(self, target: ObjectUnit[Any]) -> None: ...
    def _statement(self) -> Insert: ...
    def get_parameters(
        self,
    ) -> dict[str, SqlScalarType] | list[dict[str, SqlScalarType]]: ...
    def from_values(
        self: InsertBuilder[Unset],
        **column_values: SqlScalarType,
    ) -> InsertBuilder[Set]: ...
    def from_dataframe(
        self: InsertBuilder[Unset],
        df: pd.DataFrame,
        columns: Sequence[str] | None = ...,
    ) -> InsertBuilder[Set]: ...
    def from_select(
        self: InsertBuilder[Unset],
        select: SelectBuilder[Any, Any, Any, Any, Any],
        columns: Sequence[str] | None = ...,
    ) -> InsertBuilder[Set]: ...
    def to_sqls(
        self,
        *,
        chunk_size: int | None = ...,
        **parameters: Any,
    ) -> list[SQL]: ...
    def run(
        self,
        *,
        chunk_size: int | None = ...,
        **parameters: Any,
    ) -> tuple[int | None, pd.DataFrame]: ...
