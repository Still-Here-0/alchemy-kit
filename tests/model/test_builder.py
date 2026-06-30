from pathlib import Path

from alchemy_kit.model._builder import builder
from alchemy_kit.connect.info_builder import from_env


def test_builder_raises_on_non_dir():
    DIR = Path(__file__).resolve().parent.parent
    info = from_env(DIR / ".env")
    builder(info, DIR / "secret_model")

