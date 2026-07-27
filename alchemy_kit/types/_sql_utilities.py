from typing import TypeAlias, Literal

UnitType: TypeAlias = Literal['View', 'Table', 'Procedure']

ParameterMode: TypeAlias = Literal["IN", "OUT", "INOUT"]
