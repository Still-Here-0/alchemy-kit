from typing import Any

import pandas as pd
import sqlalchemy as sa
from sqlalchemy.schema import CreateTable

from ..connect._engine_handler import EngineHandler
from ..model.base_model import BaseModel
from ..model.units import ObjectUnit
from ..types.temp_table_types import TempTableType
from ..types.typestate import Set, Unset
from ._base import SqlBuilder

# F -> from_dataframe()
class TempBuilder[F](SqlBuilder):
    _table: sa.Table
    def __new__(
        cls,
        source: ObjectUnit[Any],
        global_temp: bool = ...,
        stage: TempTableType = ...,
    ) -> TempBuilder[Set]: ...
    def __init__(
        self,
        source: ObjectUnit[Any],
        global_temp: bool = ...,
        stage: TempTableType = ...,
    ) -> None: ...
    @classmethod
    def from_dataframe(
        cls: type[TempBuilder[Unset]],
        df: pd.DataFrame,
        handler: EngineHandler,
        name: str,
        *,
        base: type[BaseModel[Any]] | None = ...,
        global_temp: bool = ...,
    ) -> TempBuilder[Set]: ...
    def _statement(self) -> CreateTable: ...
    def unit(self) -> ObjectUnit[Any]: ...
