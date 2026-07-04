from pathlib import Path

from alchemy_kit.connect.info_builder import from_env
from alchemy_kit.model import build
from alchemy_kit.model import SchemaConfig


def test_builder_raises_on_non_dir():
    DIR = Path(__file__).resolve().parent.parent
    info = from_env(DIR / ".env")
    config = SchemaConfig()
    config.include_schema("ghcloudops")
    build(info, DIR / "secret_model", schema_config=config, clear_result_dir=True)

