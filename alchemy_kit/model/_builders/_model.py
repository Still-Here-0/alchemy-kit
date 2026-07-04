from pathlib import Path

from ...resources._better_logger import BetterLogger
from .._model.db_model import DBModel
from ._build_py_file import PyFileBuilder
from ...resources._identifiers import Identifiers
#from ._build_stub_file import


def build_model(model: DBModel, result_dir: Path, root_dir: Path, logger: BetterLogger):
    result_dir.mkdir(parents=True, exist_ok=True)
    identifiers = Identifiers()

    for schema_name, schema_data in model.schemas.items():
        init_file_data: list[str] = []
        schema_path = result_dir / identifiers.valid_explorer_name(schema_name)
        schema_path.mkdir(exist_ok=True)

        for object_name, object_data in schema_data.objects.items():
            valid_file_name = identifiers.valid_explorer_name(object_name)
            valid_obj_name = identifiers.valid_py_object_name(object_name)
            init_file_data.append(f"from .{valid_file_name} import {valid_obj_name}")

            object_path = schema_path / valid_file_name

            object_py = object_path.with_suffix(".py")
            _ = PyFileBuilder(
                schema_name=schema_name,
                class_name=valid_obj_name,
                file_path=object_py,
                object_model=object_data,
                db_dialect=model.dialect
            ).build()

            # TODO: log file name, object name and file lenght

            object_pyi = object_path.with_suffix(".pyi")

        ...

