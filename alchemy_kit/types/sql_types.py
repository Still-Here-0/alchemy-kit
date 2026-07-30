from array import array
from collections import deque
from collections.abc import ItemsView, KeysView, Sequence, Set, ValuesView
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import IntEnum, StrEnum
from typing import Final, Literal, TypeAlias
from uuid import UUID

SqlScalarType: TypeAlias = (
    # Core
    int
    | float
    | Decimal
    | str
    | bool
    | None

    # Date
    | date
    | datetime
    | time
    | timedelta

    # Binary
    | bytes
    | bytearray
    | memoryview

    # Others
    | UUID
    | StrEnum    # plain Enum is not bindable raw; only str/int-backed enums are
    | IntEnum
)

SqlExpandType: TypeAlias = Sequence[SqlScalarType] | Set[SqlScalarType]

SQL_EXPAND_CLASSES: Final = (
    list, tuple, range, deque, array,
    set, frozenset, KeysView, ValuesView, ItemsView,
)

SqlParamType: TypeAlias = SqlScalarType | SqlExpandType

SqlJoinTypes: TypeAlias = Literal[
    "INNER",
    "LEFT",
    "RIGHT",
    "FULL",
    "CROSS",
]
