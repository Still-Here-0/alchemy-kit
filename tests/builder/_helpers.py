from typing import Any, Optional, cast

import pandera.pandas as pa
import sqlalchemy
from pandera.typing import Series

from alchemy_kit.connect._engine_handler import EngineHandler
from alchemy_kit.connect._info import ConnectionInfo
from alchemy_kit.model.base_model import BaseModel, MetaData
from alchemy_kit.resources.dialects import MssqlMap, OracleMap, SqliteMap


class items(BaseModel):
    id_1: Series[int] = pa.Field(nullable=False, alias="id", metadata={"original_type": "integer"})
    name: Series[str] = pa.Field(nullable=False, alias="name", metadata={"original_type": "varchar"})
    price: Optional[Series[float]] = pa.Field(nullable=True, alias="price", metadata={"original_type": "real"})

    class Config(BaseModel.Config):
        metadata = MetaData(
            db_name=None, schema_name="main", obj_name="items", obj_type="Table",
            reference_name='"main"."items"', description=None,
        )


class parts(BaseModel):
    id_1: Series[int] = pa.Field(nullable=False, alias="id", metadata={"original_type": "integer"})
    label: Series[str] = pa.Field(nullable=False, alias="label", metadata={"original_type": "varchar"})

    class Config(BaseModel.Config):
        metadata = MetaData(
            db_name=None, schema_name="main", obj_name="parts", obj_type="Table",
            reference_name='"main"."parts"', description=None,
        )


class mssql_items(BaseModel):
    id_1: Series[int] = pa.Field(nullable=False, alias="id", metadata={"original_type": "int"})

    class Config(BaseModel.Config):
        metadata = MetaData(
            db_name="app_db", schema_name="dbo", obj_name="items", obj_type="Table",
            reference_name="[dbo].[items]", description=None,
        )


class mssql_wide(BaseModel):
    id_1: Series[int] = pa.Field(nullable=False, alias="id", metadata={"original_type": "int"})
    name: Series[str] = pa.Field(nullable=False, alias="name", metadata={"original_type": "varchar"})
    price: Optional[Series[float]] = pa.Field(nullable=True, alias="price", metadata={"original_type": "float"})

    class Config(BaseModel.Config):
        metadata = MetaData(
            db_name="app_db", schema_name="dbo", obj_name="wide", obj_type="Table",
            reference_name="[dbo].[wide]", description=None,
        )


class oracle_items(BaseModel):
    id_1: Series[int] = pa.Field(nullable=False, alias="ID", metadata={"original_type": "number"})
    name: Series[str] = pa.Field(nullable=False, alias="NAME", metadata={"original_type": "varchar2"})

    class Config(BaseModel.Config):
        metadata = MetaData(
            db_name="APPDB", schema_name="APP", obj_name="ITEMS", obj_type="Table",
            reference_name='"APP"."ITEMS"', description=None,
        )


SQLITE_HANDLER = EngineHandler(cast(Any, None), ConnectionInfo(sqlalchemy.make_url("sqlite://"), expect=SqliteMap))
MSSQL_HANDLER = EngineHandler(cast(Any, None), ConnectionInfo(sqlalchemy.make_url("mssql+pyodbc://"), expect=MssqlMap))
ORACLE_HANDLER = EngineHandler(cast(Any, None), ConnectionInfo(sqlalchemy.make_url("oracle+oracledb://"), expect=OracleMap))
