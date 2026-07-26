from pathlib import Path

from ...resources._better_logger import BetterLogger
from ...resources._identifiers import Identifiers
from .._model.db_model import DBModel
from ._build_callable_py import CallablePyFileBuilder
from ._build_callable_stub import CallableStubFileBuilder
from ._build_py_file import PyFileBuilder
from ._build_stub_file import StubFileBuilder


def build_model(model: DBModel, result_dir: Path, logger: BetterLogger):
    result_dir.mkdir(parents=True, exist_ok=True)
    package_identifiers = Identifiers()

    for schema_name, schema_data in model.schemas.items():
        init_file_data: list[str] = []
        schema_path = result_dir / package_identifiers.valid_explorer_name(schema_name)
        schema_path.mkdir(exist_ok=True)

        schema_identifiers = Identifiers()

        for object_name, object_data in schema_data.objects.items():
            valid_obj_name = schema_identifiers.valid_py_object_name(object_name)
            valid_module_name = schema_identifiers.valid_explorer_name(f"{object_name}_MODULE")
            init_file_data.append(f"from .{valid_module_name} import {valid_obj_name}")

            object_path = schema_path / valid_module_name

            object_py = object_path.with_suffix(".py")
            py_builder = PyFileBuilder(
                schema_name=schema_name,
                class_name=valid_obj_name,
                file_path=object_py,
                object_model=object_data,
                db_dialect=model.dialect
            )
            _ = py_builder.build()

            # TODO: log file name, object name and file lenght

            object_pyi = object_path.with_suffix(".pyi")
            _ = StubFileBuilder(
                schema_name=schema_name,
                class_name=valid_obj_name,
                file_path=object_pyi,
                object_model=object_data,
                db_dialect=model.dialect,
                column_names=py_builder.column_names,
            ).build()

        for procedure_name, procedure_data in schema_data.callables.items():
            valid_proc_name = schema_identifiers.valid_py_object_name(procedure_name)
            valid_module_name = schema_identifiers.valid_explorer_name(f"{procedure_name}_CALL")
            init_file_data.append(f"from .{valid_module_name} import {valid_proc_name}")

            procedure_path = schema_path / valid_module_name

            _ = CallablePyFileBuilder(
                schema_name=schema_name,
                class_name=valid_proc_name,
                file_path=procedure_path.with_suffix(".py"),
                procedure_model=procedure_data,
                db_dialect=model.dialect,
            ).build()

            _ = CallableStubFileBuilder(
                schema_name=schema_name,
                class_name=valid_proc_name,
                file_path=procedure_path.with_suffix(".pyi"),
                procedure_model=procedure_data,
                db_dialect=model.dialect,
            ).build()

        init_path = schema_path/"__init__.py"
        init_path.write_text('\n'.join(init_file_data))

    (result_dir/"__init__.py").touch()

