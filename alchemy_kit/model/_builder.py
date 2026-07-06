from logging import Logger
from pathlib import Path

from ..connect._info import ConnectionInfo
from ..resources._better_logger import BetterLogger
from . import _builders
from ._schema_config import SchemaConfig
from ._utils import clear_dir, parse_db


def build(
        conn_info: ConnectionInfo,
        result_dir: Path,
        *, 
        schema_config: SchemaConfig | None = None,
        clear_result_dir: bool = False,
        logger: Logger | BetterLogger | None = None,
    ):
    if result_dir.is_file():
        raise ValueError(f"{result_dir} is a file, expected a directory (or nonexistent path)")

    if schema_config is None:
        schema_config = SchemaConfig()

    if not isinstance(logger, BetterLogger):
        logger = BetterLogger(logger)

    if clear_result_dir:
        clear_dir(result_dir)

    # TODO: log init builder

    model = parse_db(conn_info, schema_config, logger)
    _builders.build_model(model, result_dir, logger)

def build_svg(conn_info: ConnectionInfo, result_path: Path, *, schema_config: SchemaConfig | None = None, logger: Logger | BetterLogger | None):
    if result_path.suffix != ".svg":
        result_path = result_path.with_suffix(".svg")

    if schema_config is None:
        schema_config = SchemaConfig()

    if not isinstance(logger, BetterLogger):
        logger = BetterLogger(logger)
    
    model = parse_db(conn_info, schema_config, logger)
    _builders.build_svg(model, result_path, logger)

