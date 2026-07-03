from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from ..._core.resources.dialect_map import get_type
from ..._core.resources.identifiers import static
from ..._core.types import DialectTypes
from .._model.column_model import ColumnModel
from .._model.object_model import ObjectModel
from ..base_model import BaseModel


@dataclass(kw_only=True)
class PyFileBuilder:
    template: ClassVar[Path] = Path(__file__).resolve().parent/"py_template_file.txt"
    column_template: ClassVar[str] = "{column_name}: {column_type} = pa.Field({column_parameters})"
    identifiers: set[str] = field(default_factory=lambda: set(static), init=False, repr=False)

    class_name: str
    file_path: Path
    object_model: ObjectModel
    db_dialect: DialectTypes

    def build(self) -> str:
        template = self.template.read_text("UTF-8")
        lines = template.splitlines()
        column_idx = lines.index("    :columns")

        for column_name, column_data in self.object_model.columns.items():
            column = self.column_template.format(
                column_name=column_name,
                column_type=self._get_column_type(column_data),
                column_parameters=self._get_column_parameters(column_data),
            )
            lines.insert(column_idx, column)

        file_data = "\n".join(lines)
        self.file_path.write_text(file_data, "UTF-8")
        return file_data

    def _get_column_type(self, column_model: ColumnModel) -> str:
        column_type = ""

        if column_model.is_nullable:
            column_type += "Optional["

        py_type = get_type(self.db_dialect, column_model.type)

        column_type += f"Series[{py_type}"
        column_type += ']'*column_type.count('[')

        return column_type

    def _get_column_parameters(self, column_model: ColumnModel) -> str: # TODO: Add more info, create a real column metadata
        parameters: list[str] = [f"nullable={column_model.is_nullable}"]

        if column_model.is_unique or column_model.is_primary_key:
            parameters.append("unique=True")

        if column_model.description:
            description = column_model.description.replace('"', '\\"')
            parameters.append(f'description="{description}"')

        return ", ".join(parameters)

