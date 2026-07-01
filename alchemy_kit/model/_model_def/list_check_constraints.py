from typing import Self

from pandera.pandas import Field
from pandera.typing import DataFrame, Series

from ...connect._engine_handler import EngineHandler
from ...types._sql_parameters import SqlParamters
from ..base_model import BaseModel
from .utils import get_sql


class ListCheckConstraints(BaseModel):
    """Schema for the `list_check_constraints` query result (one row per CHECK).

    ``column_name`` is the column the check is attached to for column-level
    checks, and null for table-level checks. Column order and names mirror the
    SELECT list of the dialect SQL files.
    """

    check_name: Series[str] = Field(nullable=False)
    definition: Series[str] = Field(nullable=False)
    column_name: Series[str] = Field(nullable=True)

    @classmethod
    def get_data(cls, handler: EngineHandler, schema_name: str, object_name: str) -> DataFrame[Self]:
        sql_params: SqlParamters = {"schema": schema_name, "object": object_name}
        sql = get_sql(handler, "list_check_constraints", sql_params, {})
        _, df = handler.run_sql(sql)
        return cls.validate(df)
