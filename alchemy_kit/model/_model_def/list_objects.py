from typing import Self

from pandera.pandas import Field
from pandera.typing import Series, DataFrame

from ..base_model import BaseModel
from ...connect._info import ConnectionInfo
from . import get_data


class ListObjects(BaseModel):
    """Schema for the `list_objects` query result (one row per table/view).

    Column order and names mirror the SELECT list of the dialect SQL files.
    """

    object_name: Series[str] = Field(nullable=False)
    object_type: Series[str] = Field(nullable=False)

    @classmethod
    def get_data(cls, info: ConnectionInfo) -> DataFrame[Self]:
        return cls.validate(get_data(info, "list_objects"))

