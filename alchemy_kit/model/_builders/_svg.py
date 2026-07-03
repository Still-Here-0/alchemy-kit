from pathlib import Path

from ...resources._better_logger import BetterLogger
from .._model.db_model import DBModel


def build_svg(model: DBModel, result_dir: Path, logger: BetterLogger):

    for schema in model.schemas:
        ...

