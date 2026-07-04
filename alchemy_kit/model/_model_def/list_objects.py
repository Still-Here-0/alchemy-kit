from typing import Self

from pandera.pandas import Field
from pandera.typing import DataFrame, Series

from ...connect._engine_handler import EngineHandler
from ...types._sql_parameters import SqlParamters, SqlTextReplacement
from .._schema_config import SchemaConfig
from ..base_model import BaseModel
from .utils import get_sql


class ListObjects(BaseModel):
    """Schema for the `list_objects` query result (one row per table/view).

    Column order and names mirror the SELECT list of the dialect SQL files.
    """

    object_name: Series[str] = Field(nullable=False)
    object_type: Series[str] = Field(nullable=False)

    @classmethod
    def get_data(cls, handler: EngineHandler, schema_conf: SchemaConfig, schema_name: str) -> DataFrame[Self]:
        sql_params: SqlParamters = {"schema": schema_name}
        txt_replac: SqlTextReplacement = {
            "t_include_objects": "", 
            "v_include_objects": "", 
            "t_exclude_objects": "",
            "v_exclude_objects": "",
        }

        include_data = schema_conf._include.get(schema_name)
        if include_data:
            txt_replac["t_include_objects"] = "AND t.name in :include_objects"
            txt_replac["v_include_objects"] = "AND v.name in :include_objects"
            sql_params["include_objects"] = include_data

        exclude_data = schema_conf._exclude.get(schema_name)
        if exclude_data:
            txt_replac["t_exclude_objects"] = "AND t.name not in :exclude_objects"
            txt_replac["v_exclude_objects"] = "AND v.name not in :exclude_objects"
            sql_params["exclude_objects"] = exclude_data

        sql = get_sql(handler, "list_objects", sql_params, txt_replac)
        _, df = handler.run_sql(sql)
        return cls.validate(df)

