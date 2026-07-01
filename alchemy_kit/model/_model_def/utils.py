from pathlib import Path


from ...types._sql_parameters import SqlParamters, SqlTextReplacement

from ...connect._engine_handler import EngineHandler
from ...resources._sql import SQL


def get_sql(handler: EngineHandler, file_name: str, sql_parameters: SqlParamters, text_replacements: SqlTextReplacement) -> SQL:
    sql_path = Path(__file__).resolve().parent / "_model_sqls" / handler._con_info.dialect / file_name
    sql = SQL(sql_path=sql_path, query_parameters=sql_parameters, text_replacements=text_replacements)
    sql.set_script_dir(Path())
    return sql

