from collections.abc import Mapping, Sequence
from typing import TypeAlias
from .sql_types import SqlParamType

SqlParamMap: TypeAlias = Mapping[str, SqlParamType]
SqlParamters: TypeAlias = SqlParamMap | Sequence[SqlParamMap]
SqlTextReplacement: TypeAlias = Mapping[str, str]
