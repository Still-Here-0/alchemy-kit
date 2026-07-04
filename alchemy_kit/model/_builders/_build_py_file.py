from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from ...resources._dialect_map import get_str_length, get_type
from ...resources._identifiers import Identifiers
from ...types import DialectTypes
from .._model.column_model import ColumnModel
from .._model.object_model import ObjectModel
from ._column_metadata import ColumnMetadata, ForeignKeyMeta


@dataclass(kw_only=True)
class PyFileBuilder:
    template: ClassVar[Path] = Path(__file__).resolve().parent/"py_template_file.txt"
    column_template: ClassVar[str] = "    {column_name}: {column_type} = pa.Field({column_parameters})"
    identifiers: Identifiers = field(default_factory=Identifiers, init=False, repr=False)

    schema_name: str
    class_name: str
    file_path: Path
    object_model: ObjectModel
    db_dialect: DialectTypes

    def build(self) -> str:
        template = self.template.read_text("UTF-8")
        template = template.format(
            class_name=self.class_name,
            unique=f"unique={self.object_model.get_unique_constrait()!r}",
            metadata=self._get_object_metadata(),
        )

        lines = template.splitlines()
        column_idx = lines.index("    :columns")

        for column_name, column_data in self.object_model.columns.items():
            column = self.column_template.format(
                column_name=self.identifiers.valid_py_object_name(column_name),
                column_type=self._get_column_type(column_data),
                column_parameters=self._get_column_parameters(column_data),
            )
            lines.insert(column_idx, column)
            column_idx += 1

        lines.pop(column_idx)

        file_data = '\n'.join(lines)
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

    def _get_column_parameters(self, column_model: ColumnModel) -> str:
        parameters: list[str] = [
            f"nullable={column_model.is_nullable}",
            f"alias={column_model.name!r}",
        ]

        if column_model.is_unique or column_model.is_primary_key:
            parameters.append("unique=True")

        str_length = get_str_length(self.db_dialect, column_model)
        if str_length is not None:
            parameters.append(f"str_length={{'max_value': {str_length}}}")

        if column_model.description:
            parameters.append(f"description={column_model.description!r}")

        metadata = self._build_metadata(column_model).to_dict()
        if metadata:
            parameters.append(f"metadata={metadata!r}")

        return ", ".join(parameters)

    def _build_metadata(self, column_model: ColumnModel) -> ColumnMetadata:
        foreign_key: ForeignKeyMeta | None = None
        if column_model.fk_ref is not None:
            foreign_key = ForeignKeyMeta(
                schema=column_model.fk_ref.schema,
                table=column_model.fk_ref.table,
                column=column_model.fk_ref.column,
            )

        return ColumnMetadata(
            identity=column_model.is_identity,
            computed=column_model.is_computed,
            primary_key=column_model.is_primary_key,
            has_default=column_model.has_default,
            default=column_model.default,
            scale=column_model.scale,
            precision=column_model.precision,
            collation=column_model.collation_name,
            original_type=column_model.type,
            foreign_key=foreign_key,
        )

    def _get_object_metadata(self) -> str:
        metadata = []
        metadata.append(f"schema_name={self.schema_name!r}")
        metadata.append(f"obj_name={self.object_model.name!r}")
        metadata.append(f"obj_type={self.object_model.type!r}")
        metadata.append(f"reference_name=\"[{self.schema_name}].[{self.object_model.name}]\"")
        metadata.append(f"description={self.object_model.description!r}")
        return f"metadata = MetaData({','.join(metadata)})"

