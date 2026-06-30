from pathlib import Path
import pandas as pd

from ...connect._info import ConnectionInfo
from ...connect._engine_manager import EngineManager
from ...resources._sql import SQL


def get_data(info: ConnectionInfo, file_name: str) -> pd.DataFrame:
    sql_path = Path(__file__).resolve().parent / "_model_sqls" / info.dialect / file_name
    sql = SQL(sql_path=sql_path)
    sql.set_script_dir(Path())

    with EngineManager(None) as manager:
        handler = manager.create_engine(info)
        _, data = handler.run_sql(sql)
        return data


