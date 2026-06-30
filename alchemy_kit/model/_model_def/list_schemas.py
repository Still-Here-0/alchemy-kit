from typing import Self
from pandera.pandas import Field
from pandera.typing import Series, DataFrame

from ...connect._info import ConnectionInfo
from . import get_data
from ..base_model import BaseModel


class ListSchemas(BaseModel):
    """Schema for the `list_schemas` query result (one row per user schema).

    Column order and names mirror the SELECT list of the dialect SQL files.
    """

    name: Series[str] = Field(nullable=False)

    @classmethod
    def get_data(cls, info: ConnectionInfo) -> DataFrame[Self]:
        return cls.validate(get_data(info, "list_schemas"))

