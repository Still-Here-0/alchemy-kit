from enum import StrEnum


class TempTableType(StrEnum):
    STAGE = "stage"
    STAGE_WITH_DEFAULTS = "stage_with_defaults"
    FULL = "full"
