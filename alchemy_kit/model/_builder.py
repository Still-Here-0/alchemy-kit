import shutil
from logging import Logger
from pathlib import Path
from typing import Any

import pandas as pd

from ..connect._engine_manager import EngineManager
from ..connect._info import ConnectionInfo
from ..resources._better_logger import BetterLogger
from ..resources.dir_helpers import find_project_root
from ._model.column_model import ColumnModel, ForeignKeyModel
from ._model.constraint_model import CheckConstraintModel, ForeignKeyConstraintModel
from ._model.db_model import DBModel
from ._model.object_model import ObjectModel
from ._model.schema_model import SchemaModel
from ._model_def.list_check_constraints import ListCheckConstraints
from ._model_def.list_columns import ListColumns
from ._model_def.list_columns_cluster import ListUniqueClusters
from ._model_def.list_foreign_keys import ListForeignKeys
from ._model_def.list_objects import ListObjects
from ._model_def.list_schemas import ListSchemas
from ._schema_config import SchemaConfig


def builder(
        conn_info: ConnectionInfo,
        result_dir: Path,
        *, 
        schema_config: SchemaConfig | None = None,
        clear_result_dir: bool = False,
        root_dir: Path | None = None,
        logger: Logger | BetterLogger | None = None,
    ):
    if not result_dir.is_dir():
        raise ValueError(f"Result dir not found: {result_dir}")

    if schema_config is None:
        schema_config = SchemaConfig()

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

    model = _parse_db(conn_info, schema_config)
    _build_model(model, result_dir, root_dir)

def _parse_db(conn_info: ConnectionInfo, schema_conf: SchemaConfig) -> DBModel:
    db = DBModel(conn_info.con_url.database)
    
    with EngineManager(None) as manager:
        handler = manager.create_engine(conn_info)
        schema_data = ListSchemas.get_data(handler, schema_conf)
        for _, row in schema_data.iterrows():
            schema_name: str = row[ListSchemas.name]
            sql_schema = SchemaModel(schema_name)
            db.schemas[schema_name] = sql_schema

            object_data = ListObjects.get_data(handler, schema_conf, schema_name)
            for _, row in object_data.iterrows():
                object_name: str = row[ListObjects.object_name]
                sql_object = ObjectModel(object_name)
                sql_schema.objects[object_name] = sql_object

                column_data = ListColumns.get_data(handler, schema_name, object_name)
                for _, row in column_data.iterrows():
                    fk_ref = None
                    if row[ListColumns.is_foreign_key]:
                        fk_ref = ForeignKeyModel(
                            schema=row[ListColumns.fk_ref_schema],
                            table=row[ListColumns.fk_ref_table],
                            column=row[ListColumns.fk_ref_column],
                        )

                    column = ColumnModel(
                        name=row[ListColumns.column_name],
                        column_type=row[ListColumns.sql_type],
                        is_nullable=bool(row[ListColumns.is_nullable]),
                        is_identity=bool(row[ListColumns.is_identity]),
                        is_computed=bool(row[ListColumns.is_computed]),
                        max_length=int(row[ListColumns.max_length]),
                        precision=int(row[ListColumns.precision]),
                        scale=int(row[ListColumns.scale]),
                        collation_name=_none_if_na(row[ListColumns.collation_name]),
                        has_default=bool(row[ListColumns.has_default]),
                        default=_none_if_na(row[ListColumns.default_value]),
                        is_unique=bool(row[ListColumns.is_unique]),
                        is_primary_key=bool(row[ListColumns.is_primary_key]),
                        is_foreign_key=bool(row[ListColumns.is_foreign_key]),
                        description=_none_if_na(row[ListColumns.description]),
                        fk_ref=fk_ref,
                    )
                    sql_object.columns[column.name] = column

                column_cluster_data = ListUniqueClusters.get_data(handler, schema_name, object_name)
                for _, row in column_cluster_data.iterrows():
                    if not row[ListUniqueClusters.is_unique]:
                        continue

                    col_names = [col.strip() for col in row[ListUniqueClusters.columns].split(", ")]
                    sql_object.add_unique_constrait(col_names)

                fk_data = ListForeignKeys.get_data(handler, schema_name, object_name)
                for _, row in fk_data.iterrows():
                    fk_columns = [col.strip() for col in row[ListForeignKeys.columns].split(", ")]
                    fk_ref_columns = [col.strip() for col in row[ListForeignKeys.ref_columns].split(", ")]
                    foreign_key = ForeignKeyConstraintModel(
                        name=row[ListForeignKeys.fk_name],
                        columns=fk_columns,
                        ref_schema=row[ListForeignKeys.ref_schema],
                        ref_table=row[ListForeignKeys.ref_table],
                        ref_columns=fk_ref_columns,
                        on_delete=row[ListForeignKeys.on_delete],
                        on_update=row[ListForeignKeys.on_update],
                    )
                    sql_object.foreign_keys[foreign_key.name] = foreign_key

                check_data = ListCheckConstraints.get_data(handler, schema_name, object_name)
                for _, row in check_data.iterrows():
                    check = CheckConstraintModel(
                        name=row[ListCheckConstraints.check_name],
                        definition=row[ListCheckConstraints.definition],
                        column=_none_if_na(row[ListCheckConstraints.column_name]),
                    )
                    sql_object.check_constraints[check.name] = check

    return db


def _none_if_na(value: Any) -> Any:
    """Return ``None`` for pandas null markers (NaN/NA/None), else the value."""
    return None if pd.isna(value) else value

def _build_model(model: DBModel, result_dir: Path, root_dir: Path):
    ...
