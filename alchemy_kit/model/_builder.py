import shutil
from logging import Logger
from pathlib import Path

from ..connect._info import ConnectionInfo
from ..resources._better_logger import BetterLogger
from ..resources.dir_helpers import find_project_root


def builder(
        conn_info: ConnectionInfo,
        result_dir: Path,
        *, 
        schemas: None = None,
        clear_result_dir: bool = False,
        root_dir: Path | None = None,
        logger: Logger | BetterLogger | None = None,
    ):
    if not result_dir.is_dir():
        raise ValueError("")

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

    script_folder = Path(__file__).resolve().parent / "model_scripts"
    conn_info.set_script_dir(script_folder)

    model = _parse_db(conn_info, schemas)
    _build_model(model, result_dir, root_dir)

def _parse_db(conn_info: ConnectionInfo, schemas: None = None) -> None:
    ...

def _build_model(model: None, result_dir: Path, root_dir: Path):
    ...
