
import shutil
from pathlib import Path
from typing import Any, cast

import pandas as pd

from ..connect._engine_manager import EngineManager
from ..connect._info import ConnectionInfo
from ..resources._better_logger import BetterLogger
from ..types._sql_utilities import ParameterMode, UnitType
from ._model.column_model import ColumnModel, ForeignKeyModel
from ._model.constraint_model import CheckConstraintModel, FilteredUniqueIndexModel, ForeignKeyConstraintModel
from ._model.db_model import DBModel
from ._model.object_model import ObjectModel
from ._model.procedure_model import ParameterModel, ProcedureModel
from ._model.schema_model import SchemaModel
from ._model_def import (
    ListCheckConstraints,
    ListColumns,
    ListForeignKeys,
    ListObjects,
    ListParameters,
    ListProcedures,
    ListSchemas,
    ListUniqueClusters,
    MetadataExtractor,
)
from ._schema_config import SchemaConfig


def clear_dir(dir: Path):
    for item in dir.iterdir():
        if not item.name.startswith('.'):
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

def parse_db(conn_info: ConnectionInfo, schema_conf: SchemaConfig, logger: BetterLogger) -> DBModel:
    db = DBModel(conn_info.con_url.database, conn_info.dialect)
    
    with EngineManager(None) as manager:
        handler = manager.create_engine(conn_info)
        extractor = MetadataExtractor(handler)
        schema_data = extractor.list_schemas(schema_conf)
        for _, row in schema_data.iterrows():
            schema_name: str = row[ListSchemas.name]
            sql_schema = SchemaModel(schema_name)
            db.schemas[schema_name] = sql_schema

            object_data = extractor.list_objects(schema_conf, schema_name)
            for _, row in object_data.iterrows():
                object_name: str = row[ListObjects.object_name]
                object_type: UnitType = row[ListObjects.object_type]
                object_desc: str | None = none_if_na(row[ListObjects.object_description])
                sql_object = ObjectModel(object_name, object_type, object_desc)
                sql_schema.objects[object_name] = sql_object

                column_data = extractor.list_columns(schema_name, object_name)
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
                        collation_name=none_if_na(row[ListColumns.collation_name]),
                        has_default=bool(row[ListColumns.has_default]),
                        default=none_if_na(row[ListColumns.default_value]),
                        is_unique=bool(row[ListColumns.is_unique]),
                        is_primary_key=bool(row[ListColumns.is_primary_key]),
                        is_foreign_key=bool(row[ListColumns.is_foreign_key]),
                        description=none_if_na(row[ListColumns.description]),
                        fk_ref=fk_ref,
                    )
                    sql_object.columns[column.name] = column

                column_cluster_data = extractor.list_unique_clusters(schema_name, object_name)
                for _, row in column_cluster_data.iterrows():
                    if not row[ListUniqueClusters.is_unique]:
                        continue

                    col_names = [col.strip() for col in row[ListUniqueClusters.columns].split(", ")]
                    filter_definition = none_if_na(row[ListUniqueClusters.filter_definition])

                    if filter_definition is not None:
                        filtered_index = FilteredUniqueIndexModel(
                            name=row[ListUniqueClusters.key_name],
                            columns=col_names,
                            definition=filter_definition,
                        )
                        sql_object.filtered_unique_indexes[filtered_index.name] = filtered_index
                    else:
                        sql_object.add_unique_constrait(col_names)

                fk_data = extractor.list_foreign_keys(schema_name, object_name)
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

                check_data = extractor.list_check_constraints(schema_name, object_name)
                for _, row in check_data.iterrows():
                    check = CheckConstraintModel(
                        name=row[ListCheckConstraints.check_name],
                        definition=row[ListCheckConstraints.definition],
                        column=none_if_na(row[ListCheckConstraints.column_name]),
                    )
                    sql_object.check_constraints[check.name] = check

            procedure_data = extractor.list_procedures(schema_conf, schema_name)
            for _, row in procedure_data.iterrows():
                procedure_name: str = row[ListProcedures.procedure_name]
                procedure = ProcedureModel(
                    name=procedure_name,
                    description=none_if_na(row[ListProcedures.procedure_description]),
                )
                sql_schema.callables[procedure_name] = procedure

                parameter_data = extractor.list_parameters(schema_name, procedure_name)
                for _, row in parameter_data.iterrows():
                    parameter = ParameterModel(
                        name=row[ListParameters.parameter_name],
                        parameter_type=row[ListParameters.sql_type],
                        is_nullable=bool(row[ListParameters.is_nullable]),
                        mode=cast(ParameterMode, row[ListParameters.mode]),
                        ordinal=int(row[ListParameters.ordinal]),
                    )
                    procedure.add_parameter(parameter)

    return db

def none_if_na(value: Any) -> Any:
    return None if pd.isna(value) else value

