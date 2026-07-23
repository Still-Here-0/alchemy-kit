from typing import Any

import pandas as pd
import sqlalchemy as sa
from pandas.api import types as pdt

from ..model.base_model import BaseModel


class DataFrameTemp(BaseModel):
    """Placeholder base for temp tables built from a raw DataFrame, whose
    column names are their own SQL names."""


def sa_type_from_series(series: pd.Series) -> sa.types.TypeEngine[Any]:
    """Infer a portable SQLAlchemy column type from a DataFrame column."""
    if pdt.is_bool_dtype(series):
        return sa.Boolean()
    if pdt.is_integer_dtype(series):
        return sa.BigInteger()
    if pdt.is_float_dtype(series):
        return sa.Float()
    if pdt.is_datetime64_any_dtype(series):
        return sa.DateTime()
    if pdt.is_timedelta64_dtype(series):
        return sa.Interval()

    lengths = series.dropna().astype(str).str.len()
    return sa.String(max(int(lengths.max()) if not lengths.empty else 1, 1))
