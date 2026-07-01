from typing import Self

from pandera.pandas import Field
from pandera.typing import DataFrame, Series

from ...connect._engine_handler import EngineHandler
from ...types._sql_parameters import SqlParamters
from ..base_model import BaseModel
from .utils import get_sql


class ListForeignKeys(BaseModel):
    """Schema for the `list_foreign_keys` query result (one row per FK constraint).

    ``columns`` and ``ref_columns`` are comma-separated, key-ordinal ordered and
    parallel: the i-th local column references the i-th referenced column.
    Column order and names mirror the SELECT list of the dialect SQL files.
    """

    fk_name: Series[str] = Field(nullable=False)
    ref_schema: Series[str] = Field(nullable=False)
    ref_table: Series[str] = Field(nullable=False)
    columns: Series[str] = Field(nullable=False)
    ref_columns: Series[str] = Field(nullable=False)
    on_delete: Series[str] = Field(nullable=False)
    on_update: Series[str] = Field(nullable=False)

    @classmethod
    def get_data(cls, handler: EngineHandler, schema_name: str, object_name: str) -> DataFrame[Self]:
        sql_params: SqlParamters = {"schema": schema_name, "object": object_name}
        sql = get_sql(handler, "list_foreign_keys", sql_params, {})
        _, df = handler.run_sql(sql)
        return cls.validate(df)
