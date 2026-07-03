from pathlib import Path

from alchemy_kit.connect.info_builder import from_env
from alchemy_kit.model._builder import build


def test_builder_raises_on_non_dir():
    DIR = Path(__file__).resolve().parent.parent
    info = from_env(DIR / ".env")
    build(info, DIR / "secret_model")

