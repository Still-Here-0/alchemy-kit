from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from ...resources.dialect_map import get_codegen_imports, render_reference
from ...types import DialectTypes, sql_type_parameters
from .._model.procedure_model import ProcedureModel
from ..callable_model import CallableModel


@dataclass(kw_only=True)
class CallablePyFileBuilder:
    template: ClassVar[Path] = Path(__file__).resolve().parent / "callable_py_template.txt"

    schema_name: str
    class_name: str
    file_path: Path
    procedure_model: ProcedureModel
    db_dialect: DialectTypes

    def build(self) -> str:
        _, _, type_parameters = get_codegen_imports(self.db_dialect)

        file_data = self.template.read_text("UTF-8").format(
            class_name=self.class_name,
            callable_model_module=CallableModel.__module__,
            type_parameters_module=sql_type_parameters.__name__,
            type_parameters=type_parameters,
            metadata=self._get_metadata(),
        )

        self.file_path.write_text(file_data, "UTF-8")
        return file_data

    def _get_metadata(self) -> str:
        parameters = [
            {
                "name": parameter.name,
                "sql_type": parameter.type,
                "is_nullable": parameter.is_nullable,
                "mode": parameter.mode,
            }
            for parameter in self.procedure_model.ordered_parameters()
        ]

        metadata = [
            f"schema_name={self.schema_name!r}",
            f"name={self.procedure_model.name!r}",
            f"reference_name={render_reference(self.db_dialect, self.schema_name, self.procedure_model.name)!r}",
            f"description={self.procedure_model.description!r}",
            f"parameters={parameters!r}",
        ]

        return f"metadata = CallMetaData({', '.join(metadata)})"
