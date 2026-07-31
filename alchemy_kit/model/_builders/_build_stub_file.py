from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from ...connect._engine_handler import EngineHandler
from ...resources.dialect_map import get_type
from ...types import DialectTypes
from .._model.column_model import ColumnModel
from .._model.object_model import ObjectModel
from ..base_model import BaseModel
from .. import units


@dataclass(kw_only=True)
class StubFileBuilder:
    template: ClassVar[Path] = Path(__file__).resolve().parent/"stub_template_file.txt"

    schema_name: str
    class_name: str
    file_path: Path
    object_model: ObjectModel
    db_dialect: DialectTypes
    column_names: dict[str, str]

    def build(self) -> str:
        template = self.template.read_text("UTF-8").format(
            class_name=self.class_name,
            base_model_module=BaseModel.__module__,
            engine_handler_module=EngineHandler.__module__,
            object_unit_module=units.__name__,
            column_unit_module=units.__name__,
        )

        columns = [
            (self.column_names[name], column_model)
            for name, column_model in self.object_model.columns.items()
        ]

        model_columns = [
            f"    {name}: {self._get_column_type(column_model)}"
            for name, column_model in columns
        ]
        unit_columns = [
            f"    {name}: ColumnUnit[T]"
            for name, _ in columns
        ]

        lines = template.splitlines()
        self._replace_marker(lines, "    :columns", model_columns)
        self._replace_marker(lines, "    :unit_columns", unit_columns)

        file_data = '\n'.join(lines)
        self.file_path.write_text(file_data, "UTF-8")
        return file_data

    def _get_column_type(self, column_model: ColumnModel) -> str:
        py_type = get_type(self.db_dialect, column_model.type)
        return f"Series[{py_type}]"

    @staticmethod
    def _replace_marker(lines: list[str], marker: str, block: list[str]) -> None:
        idx = lines.index(marker)
        lines[idx:idx + 1] = block or ["    ..."]
