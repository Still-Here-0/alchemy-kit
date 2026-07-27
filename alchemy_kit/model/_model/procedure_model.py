from ...types._sql_utilities import ParameterMode, UnitType


class ParameterModel:

    def __init__(
        self,
        name: str,
        parameter_type: str,
        is_nullable: bool,
        mode: ParameterMode,
        ordinal: int,
    ) -> None:
        self.name = name
        self.type = parameter_type
        self.is_nullable = is_nullable
        self.mode = mode
        self.ordinal = ordinal


class ProcedureModel:

    def __init__(self, name: str, description: str | None) -> None:
        self.name = name
        self.type: UnitType = "Procedure"
        self.description = description
        self.parameters: list[ParameterModel] = []

    def add_parameter(self, parameter: ParameterModel) -> None:
        self.parameters.append(parameter)

    def ordered_parameters(self) -> list[ParameterModel]:
        return sorted(self.parameters, key=lambda parameter: parameter.ordinal)
