import shutil
from logging import Logger
from pathlib import Path

from ..connect._info import ConnectionInfo
from ..resources._better_logger import BetterLogger
from ..resources.dir_helpers import find_project_root
from ._schema_config import SchemaConfig
from ._model_def import list_columns, list_columns_cluster, list_objects, list_schemas


def builder(
        conn_info: ConnectionInfo,
        result_dir: Path,
        *, 
        schema_config: SchemaConfig | None = None,
        clear_result_dir: bool = False,
        root_dir: Path | None = None,
        logger: Logger | BetterLogger | None = None,
    ):
    if not result_dir.is_dir():
        raise ValueError(f"Result dir not found: {result_dir}")

    if schema_config is None:
        schema_config = SchemaConfig()

    if root_dir is None:
        root_dir = find_project_root()

    if not isinstance(logger, BetterLogger):
        logger = BetterLogger(logger)

    if clear_result_dir:
        for item in result_dir.iterdir():
            if not item.name.startswith('.'):
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()

    # TODO: log init builder

    model = _parse_db(conn_info, schema_config)
    _build_model(model, result_dir, root_dir)

def _parse_db(conn_info: ConnectionInfo, schemas: SchemaConfig) -> None:
    ...

def _build_model(model: None, result_dir: Path, root_dir: Path):
    ...
