from typing import Self

from pandera.pandas import Field
from pandera.typing import DataFrame, Series

from ...connect._engine_handler import EngineHandler
from ...types._sql_parameters import SqlParamters
from ..base_model import BaseModel
from .utils import get_sql


class ListColumns(BaseModel):
    """Schema for the `list_columns` query result (one row per table/view column).

    Column order and names mirror the SELECT list of the dialect SQL files.
    """

    column_name: Series[str] = Field(nullable=False)
    sql_type: Series[str] = Field(nullable=False)
    is_nullable: Series[bool] = Field(nullable=False)
    is_identity: Series[bool] = Field(nullable=False)
    is_computed: Series[bool] = Field(nullable=False)
    max_length: Series[int] = Field(nullable=False)
    precision: Series[int] = Field(nullable=False)
    scale: Series[int] = Field(nullable=False)
    collation_name: Series[str] = Field(nullable=True)
    has_default: Series[bool] = Field(nullable=False)
    default_value: Series[str] = Field(nullable=True)
    is_unique: Series[bool] = Field(nullable=False)
    is_primary_key: Series[bool] = Field(nullable=False)
    is_foreign_key: Series[bool] = Field(nullable=False)
    fk_ref_schema: Series[str] = Field(nullable=True)
    fk_ref_table: Series[str] = Field(nullable=True)
    fk_ref_column: Series[str] = Field(nullable=True)
    description: Series[str] = Field(nullable=True)


    @classmethod
    def get_data(cls, handler: EngineHandler, schema_name: str, object_name: str) -> DataFrame[Self]:
        sql_params: SqlParamters = {"schema": schema_name, "object": object_name}
        sql = get_sql(handler, "list_columns", sql_params, {})
        _, df = handler.run_sql(sql)
        return cls.validate(df)
