from pathlib import Path

from alchemy_kit import connect as akc
from alchemy_kit import model as akm
from alchemy_kit import builder as akb

test_folder = Path(__file__).parent
conn = akc.info_builder.from_env(test_folder/".env")
print(conn.dialect)

config = akm.SchemaConfig()
config.include_schema("ghcloudops")

akm.build(conn, test_folder/"secret_model", schema_config=config, clear_result_dir=True)

