from typing import Mapping, Sequence, TypeAlias
from .sql_types import SqlParamType

SqlParamMap: TypeAlias = Mapping[str, SqlParamType]
SqlParamters: TypeAlias = SqlParamMap | Sequence[SqlParamMap]
SqlTextReplacement: TypeAlias = Mapping[str, str]
