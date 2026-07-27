from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from ...resources._identifiers import Identifiers
from ...resources.dialect_map import get_codegen_imports, get_str_length, get_type, render_reference
from ...types import DialectTypes, sql_type_parameters
from ...types.model_metadata import ForeignKeyMeta
from .._model.column_model import ColumnModel
from .._model.constraint_model import CheckConstraintModel, FilteredUniqueIndexModel
from .._model.object_model import ObjectModel
from ..base_model import BaseModel
from ._check_parser import ColumnComparisonCheck, IndexFilterCondition, parse_column_check, parse_index_filter, parse_table_check
from ._column_metadata import ColumnMetadata


@dataclass(kw_only=True)
class PyFileBuilder:
    template: ClassVar[Path] = Path(__file__).resolve().parent/"py_template_file.txt"
    column_template: ClassVar[str] = "    {column_name}: {column_type} = pa.Field({column_parameters})"
    identifiers: Identifiers = field(default_factory=Identifiers, init=False, repr=False)
    column_names: dict[str, str] = field(default_factory=dict, init=False, repr=False)

    schema_name: str
    class_name: str
    file_path: Path
    object_model: ObjectModel
    db_dialect: DialectTypes

    def __post_init__(self) -> None:
        self.column_names = {
            name: self.identifiers.valid_py_object_name(name)
            for name in self.object_model.columns
        }

    def build(self) -> str:
        _, _, type_parameters = get_codegen_imports(self.db_dialect)
        check_methods, unparsed_table_checks = self._build_table_checks()
        index_methods, unparsed_indexes = self._build_index_checks()
        check_methods += index_methods

        template = self.template.read_text("UTF-8")
        template = template.format(
            class_name=self.class_name,
            base_model_module=BaseModel.__module__,
            type_parameters_module=sql_type_parameters.__name__,
            type_parameters=type_parameters,
            unique=f"unique={self.object_model.get_unique_constrait()!r}",
            metadata=self._get_object_metadata(unparsed_table_checks, unparsed_indexes),
        )

        lines = template.splitlines()
        column_idx = lines.index("    :columns")

        for column_name, column_data in self.object_model.columns.items():
            column = self.column_template.format(
                column_name=self.column_names[column_name],
                column_type=self._get_column_type(column_data),
                column_parameters=self._get_column_parameters(column_data),
            )
            lines.insert(column_idx, column)
            column_idx += 1

        lines.pop(column_idx)

        checks_idx = lines.index("    :checks")
        if check_methods:
            lines[checks_idx:checks_idx + 1] = ["\n\n".join(check_methods)]
        else:
            del lines[checks_idx - 1:checks_idx + 1]

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

        check_args, unparsed_checks = self._build_column_checks(column_model)
        parameters.extend(f"{name}={value!r}" for name, value in check_args.items())

        metadata = self._build_metadata(column_model, unparsed_checks).to_dict()
        if metadata:
            parameters.append(f"metadata={metadata!r}")

        return ", ".join(parameters)

    def _column_checks(self, column_name: str) -> list[CheckConstraintModel]:
        return [
            check for check in self.object_model.check_constraints.values()
            if check.column == column_name
        ]

    def _build_column_checks(self, column_model: ColumnModel) -> tuple[dict[str, Any], dict[str, str]]:
        check_args: dict[str, Any] = {}
        unparsed: dict[str, str] = {}

        for check in self._column_checks(column_model.name):
            args = parse_column_check(check.definition, self.db_dialect, column_model.name)

            if args is None or args.keys() & check_args.keys():
                unparsed[check.name] = check.definition
            else:
                check_args.update(args)

        return check_args, unparsed

    def _build_table_checks(self) -> tuple[list[str], dict[str, str]]:
        methods: list[str] = []
        unparsed: dict[str, str] = {}

        for check in self.object_model.check_constraints.values():
            if check.column is not None:
                continue

            comparison = parse_table_check(check.definition, self.db_dialect)
            known_columns = (
                comparison is not None
                and comparison.left_column in self.object_model.columns
                and comparison.right_column in self.object_model.columns
            )

            if comparison is None or not known_columns:
                unparsed[check.name] = check.definition
            else:
                methods.append(self._render_check_method(check.name, comparison))

        return methods, unparsed

    def _build_index_checks(self) -> tuple[list[str], dict[str, str]]:
        methods: list[str] = []
        unparsed: dict[str, str] = {}

        for index in self.object_model.filtered_unique_indexes.values():
            conditions = parse_index_filter(index.definition, self.db_dialect)
            condition_columns = {condition.column for condition in conditions or []}
            known_columns = set(index.columns) | condition_columns

            if conditions is None or not known_columns <= set(self.object_model.columns):
                unparsed[index.name] = f"UNIQUE ({', '.join(index.columns)}) WHERE {index.definition}"
            else:
                methods.append(self._render_index_check_method(index, conditions))

        return methods, unparsed

    def _render_index_check_method(self, index: FilteredUniqueIndexModel, conditions: list[IndexFilterCondition]) -> str:
        method_name = self.identifiers.valid_py_object_name(index.name)
        mask = " & ".join(self._render_filter_term(condition) for condition in conditions)

        return (
            f"    @pa.dataframe_check(description={index.name!r})\n"
            f"    def {method_name}(cls, df: pd.DataFrame) -> \"pd.Series[bool]\":\n"
            f"        masked = df[{mask}]\n"
            f"        return ~masked.duplicated(subset={index.columns!r}, keep=False).reindex(df.index, fill_value=False)"
        )

    @staticmethod
    def _render_filter_term(condition: IndexFilterCondition) -> str:
        if condition.operator == "is_not_null":
            return f"df[{condition.column!r}].notna()"

        if condition.operator == "!=":
            return (
                f"(df[{condition.column!r}].notna()"
                f" & (df[{condition.column!r}] != {condition.value!r}))"
            )

        return f"(df[{condition.column!r}] == {condition.value!r})"

    def _render_check_method(self, check_name: str, comparison: ColumnComparisonCheck) -> str:
        method_name = self.identifiers.valid_py_object_name(check_name)

        expression = (
            f"(df[{comparison.left_column!r}] {comparison.py_operator}"
            f" df[{comparison.right_column!r}])"
        )
        for column_name in (comparison.left_column, comparison.right_column):
            if self.object_model.columns[column_name].is_nullable:
                expression += f" | df[{column_name!r}].isna()"

        return (
            f"    @pa.dataframe_check(description={check_name!r})\n"
            f"    def {method_name}(cls, df: pd.DataFrame) -> \"pd.Series[bool]\":\n"
            f"        return {expression}"
        )

    def _build_metadata(self, column_model: ColumnModel, unparsed_checks: dict[str, str]) -> ColumnMetadata:
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
            check_constraints=unparsed_checks or None,
        )

    def _get_object_metadata(self, unparsed_checks: dict[str, str], unparsed_indexes: dict[str, str]) -> str:
        metadata = []
        metadata.append(f"schema_name={self.schema_name!r}")
        metadata.append(f"obj_name={self.object_model.name!r}")
        metadata.append(f"obj_type={self.object_model.type!r}")
        metadata.append(f"reference_name={render_reference(self.db_dialect, self.schema_name, self.object_model.name)!r}")
        metadata.append(f"description={self.object_model.description!r}")

        if unparsed_checks:
            metadata.append(f"unparsed_checks={unparsed_checks!r}")

        if unparsed_indexes:
            metadata.append(f"unparsed_indexes={unparsed_indexes!r}")

        return f"metadata = MetaData({','.join(metadata)})"

