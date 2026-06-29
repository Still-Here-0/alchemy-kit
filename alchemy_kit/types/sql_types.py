from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import IntEnum, StrEnum
from typing import Literal, TypeAlias
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

SqlExpandType: TypeAlias = list | set | tuple

SqlParamType: TypeAlias = SqlScalarType | SqlExpandType

SqlOrderTypes: TypeAlias = Literal["DESC", "ASC"]

SqlBooleanOperations: TypeAlias = Literal[
    "=",
    "!=",
    "<>",
    ">",
    "<",
    ">=",
    "<=",
    "LIKE",
    "IS",
    "IN",
    "NOT LIKE",
    "IS NOT",
    "NOT IN",
]

SqlJoinTypes: TypeAlias = Literal[
    "INNER",
    "LEFT",
    "RIGHT",
    "FULL",
    "CROSS",
]
