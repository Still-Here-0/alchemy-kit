from typing import Sequence, TypeAlias
from .sql_types import SqlParamType

SqlParamMap: TypeAlias = dict[str, SqlParamType]
SqlParamters: TypeAlias = SqlParamMap | Sequence[SqlParamMap]
SqlTextReplacement: TypeAlias = dict[str, str]

