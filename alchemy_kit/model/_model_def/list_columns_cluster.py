from typing import Self
from pandera.pandas import Field
from pandera.typing import Series, DataFrame

from ..base_model import BaseModel
from ...connect._info import ConnectionInfo
from . import get_data


class ListColumnsCluster(BaseModel):
    """Schema for the `list_columns_clusters` query result.

    One row per multi-column key/index (PK or unique) on a table/view.
    Column order and names mirror the SELECT list of the dialect SQL files.
    """

    key_name: Series[str] = Field(nullable=False)
    is_primary_key: Series[bool] = Field(nullable=False)
    is_unique_constraint: Series[bool] = Field(nullable=False)
    is_unique: Series[bool] = Field(nullable=False)
    index_type: Series[str] = Field(nullable=False)
    column_count: Series[int] = Field(nullable=False)
    columns: Series[str] = Field(nullable=False)


    @classmethod
    def get_data(cls, info: ConnectionInfo) -> DataFrame[Self]:
        return cls.validate(get_data(info, "list_columns_clusters"))

