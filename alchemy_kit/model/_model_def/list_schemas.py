from typing import Self
from pandera.pandas import Field
from pandera.typing import Series, DataFrame


from ...connect._engine_handler import EngineHandler
from ...types._sql_parameters import SqlParamters, SqlTextReplacement
from .utils import get_sql
from ..base_model import BaseModel
from .._schema_config import SchemaConfig


class ListSchemas(BaseModel):
    """Schema for the `list_schemas` query result (one row per user schema).

    Column order and names mirror the SELECT list of the dialect SQL files.
    """

    name: Series[str] = Field(nullable=False)

    @classmethod
    def get_data(cls, handler: EngineHandler, schema_conf: SchemaConfig) -> DataFrame[Self]:
        sql_params: SqlParamters = {}
        txt_replac: SqlTextReplacement = {"include_schema": "", "exclude_schema": ""}

        include = [schema for schema in schema_conf._include.keys()]
        if include:
            txt_replac["include_schema"] = "AND [name] in :include"
            sql_params["include"] = include

        exclude = [schema for schema in schema_conf._exclude.keys()]
        if exclude:
            txt_replac["exclude_schema"] = "AND [name] not in :exclude"
            sql_params["exclude"] = exclude

        sql = get_sql(handler, "list_schemas", sql_params, txt_replac)
        _, df = handler.run_sql(sql)
        return cls.validate(df)

