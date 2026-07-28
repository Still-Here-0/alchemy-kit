from typing import Any

import pandas as pd
from pandas.api import types as pdt


def none_if_na(value: Any) -> Any:
    """Map a pandas missing marker to ``None`` so it binds as SQL ``NULL``."""
    return None if pdt.is_scalar(value) and pd.isna(value) else value
