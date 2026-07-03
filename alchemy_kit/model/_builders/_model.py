from pathlib import Path

from ...resources._better_logger import BetterLogger
from .._model.object_model import ObjectModel
from .._model.db_model import DBModel
from ._build_py_file import PyFileBuilder


def build_model(model: DBModel, result_dir: Path, root_dir: Path, logger: BetterLogger):
    result_dir.mkdir(parents=True, exist_ok=True)
    
    for schema_name, schema_data in model.schemas.items():
        schema_path = result_dir / schema_name
        schema_path.mkdir(exist_ok=True)

        for object_name, object_data in schema_data.objects.items():
            object_path = schema_path / object_name
            
            object_py   = object_path.with_suffix(".py")
            PyFileBuilder(class_name="", file_path=object_py, object_model=object_data, db_dialect=model.dialect)

            object_pyi  = object_path.with_suffix(".pyi")

def build_py_file(schema_name: str, object_data: ObjectModel, file_path: Path):
    ...

def build_pyi_file(schema_name: str, object_data: ObjectModel, file_path: Path):
    ...
