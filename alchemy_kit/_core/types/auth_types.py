from typing import Literal, TypeAlias, Union

SqlAuth = Literal["SQL-Auth"]
MicrosoftAuth = Literal["Microsoft-Auth"]
AuthType: TypeAlias = Union[SqlAuth, MicrosoftAuth]
