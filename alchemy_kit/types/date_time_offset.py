import datetime
from collections.abc import Iterable
from typing import Any, cast

import numpy as np
import pandas as pd
from pandera import dtypes, errors
from pandera.backends.pandas import error_formatters
from pandera.engines import pandas_engine
from pandera.engines.type_aliases import PandasObject

__all__ = ["DateTimeOffset", "holds_offset_datetimes"]


def _is_offset_datetime(value: Any) -> bool:
    return isinstance(value, datetime.datetime) and value.utcoffset() is not None


def holds_offset_datetimes(series: pd.Series) -> bool:
    """Whether ``series`` is an object column whose non-null values are all
    timezone-aware datetimes (the :class:`DateTimeOffset` representation)."""
    if series.dtype != np.dtype("object"):
        return False

    values = series.dropna()
    return not values.empty and bool(values.map(_is_offset_datetime).all())


@dtypes.immutable(init=True)
class DateTimeOffset(pandas_engine.DataType, dtypes.Timestamp):
    """Timezone-aware timestamps that keep each row's own UTC offset.

    A ``datetime64`` column holds a single timezone, so values live in an
    ``object`` column as timezone-aware :class:`pandas.Timestamp` objects.
    Naive values are rejected: their offset is unknown.
    """

    type = np.dtype("object")

    def coerce_value(self, value: Any) -> pd.Timestamp | None:
        if value is None or value is pd.NA or value is pd.NaT:
            return None
        if isinstance(value, float) and np.isnan(value):
            return None

        timestamp = pd.Timestamp(value)
        if timestamp.tzinfo is None:
            raise ValueError(f"{value!r} has no timezone offset")
        return timestamp

    def coerce(self, data_container: PandasObject) -> PandasObject:
        series = cast(pd.Series, data_container)
        coerced: list[pd.Timestamp | None] = []
        failed: list[bool] = []

        for value in series:
            try:
                coerced.append(self.coerce_value(value))
                failed.append(False)
            except (TypeError, ValueError):
                coerced.append(None)
                failed.append(True)

        if any(failed):
            raise errors.ParserError(
                f"Could not coerce {type(series)} data_container into type {self}",
                failure_cases=error_formatters.reshape_failure_cases(
                    series[failed], ignore_na=False
                ),
            )

        return pd.Series(coerced, index=series.index, name=series.name, dtype=object)

    def check(
        self,
        pandera_dtype: dtypes.DataType,
        data_container: PandasObject | None = None,
    ) -> bool | Iterable[bool]:
        if not pandas_engine.DataType.check(self, pandera_dtype, data_container):
            return False if data_container is None else np.full(len(data_container), False)
        if data_container is None:
            return True

        return data_container.map(lambda value: pd.isna(value) or _is_offset_datetime(value))

    def __str__(self) -> str:
        return "DateTimeOffset"


pandas_engine.Engine.register_dtype(DateTimeOffset)
