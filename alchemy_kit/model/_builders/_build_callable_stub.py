from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from ...connect._engine_handler import EngineHandler
from ...resources._identifiers import Identifiers
from ...resources._sql import SQL
from ...resources.dialect_map import get_type
from ...types import DialectTypes
from .. import units
from .._model.procedure_model import ParameterModel, ProcedureModel
from ..callable_model import CallableModel


@dataclass(kw_only=True)
class CallableStubFileBuilder:
    template: ClassVar[Path] = Path(__file__).resolve().parent / "callable_stub_template.txt"
    identifiers: Identifiers = field(default_factory=Identifiers, init=False, repr=False)

    schema_name: str
    class_name: str
    file_path: Path
    procedure_model: ProcedureModel
    db_dialect: DialectTypes

    def build(self) -> str:
        file_data = self.template.read_text("UTF-8").format(
            class_name=self.class_name,
            callable_model_module=CallableModel.__module__,
            engine_handler_module=EngineHandler.__module__,
            call_unit_module=units.__name__,
            sql_module=SQL.__module__,
        )

        file_data = file_data.replace(":params", self._render_parameters())

        self.file_path.write_text(file_data, "UTF-8")
        return file_data

    def _render_parameters(self) -> str:
        return "".join(
            f", {self.identifiers.valid_py_object_name(parameter.name)}: {self._parameter_type(parameter)}"
            for parameter in self.procedure_model.ordered_parameters()
        )

    def _parameter_type(self, parameter: ParameterModel) -> str:
        py_type = get_type(self.db_dialect, parameter.type)
        return f"Optional[{py_type}]" if parameter.is_nullable else py_type
