import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd
from pandera.typing import DataFrame
from sqlalchemy.engine.interfaces import ReflectedCheckConstraint, ReflectedUniqueConstraint
from sqlalchemy.exc import NoSuchTableError

from ...connect._engine_handler import EngineHandler
from ...resources._sql import SQL
from ...resources.dialect_map import DialectMap, ReflectedTypeFacts, get_map
from ...types.dialect_types import DialectTypes
from .._schema_config import SchemaConfig
from ._frames import (
    ListCheckConstraints,
    ListColumns,
    ListForeignKeys,
    ListObjects,
    ListParameters,
    ListProcedures,
    ListSchemas,
    ListUniqueClusters,
)

_INFO_SCHEMA_ROUTINE_DIALECTS: frozenset[DialectTypes] = frozenset({
    DialectTypes.MSSQL,
    DialectTypes.MYSQL,
    DialectTypes.MARIADB,
    DialectTypes.POSTGRESQL,
})

_SYSTEM_SCHEMAS: dict[DialectTypes, frozenset[str]] = {
    DialectTypes.MSSQL: frozenset({"information_schema", "sys", "guest"}),
    DialectTypes.MYSQL: frozenset({"information_schema", "performance_schema", "mysql", "sys"}),
    DialectTypes.MARIADB: frozenset({"information_schema", "performance_schema", "mysql", "sys"}),
    DialectTypes.POSTGRESQL: frozenset({"information_schema", "pg_catalog", "pg_toast"}),
    DialectTypes.SQLITE: frozenset(),
    DialectTypes.ORACLE: frozenset({
        "sys", "system", "outln", "xdb", "ctxsys", "mdsys", "ordsys", "orddata",
        "dbsnmp", "appqossys", "wmsys", "olapsys", "lbacsys", "gsmadmin_internal",
    }),
}

_SYSTEM_SCHEMA_PREFIXES: dict[DialectTypes, tuple[str, ...]] = {
    DialectTypes.MSSQL: ("db_",),
    DialectTypes.POSTGRESQL: ("pg_",),
}

_FALLBACK_SQL_DIR = Path(__file__).parent / "_sql"

_UNIQUE_CONSTRAINTS_FALLBACK_SQL: dict[DialectTypes, str] = {
    DialectTypes.MSSQL: "mssql_unique_constraints",
}

_CHECK_CONSTRAINTS_FALLBACK_SQL: dict[DialectTypes, str] = {
    DialectTypes.MSSQL: "mssql_check_constraints",
}


class MetadataExtractor:
    """Database metadata extraction backed by ``sqlalchemy.Inspector``.

    Dialect-independent: every frame is produced from reflection and validated
    by the pandera schemas in ``_frames``, so ``parse_db`` consumes one uniform
    shape regardless of the connected database.
    """

    def __init__(self, handler: EngineHandler) -> None:
        self._handler = handler
        self._inspector = handler.get_inspector()
        self._dialect: DialectTypes = handler._con_info.dialect
        self._columns_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}

    def list_schemas(self, schema_conf: SchemaConfig) -> DataFrame[ListSchemas]:
        names = [
            name for name in self._inspector.get_schema_names()
            if not self._is_system_schema(name)
        ]

        include = set(schema_conf._include.keys())
        if include:
            names = [name for name in names if name in include]

        exclude = {
            name for name, objects in schema_conf._exclude.items()
            if not objects
        }
        names = [name for name in names if name not in exclude]

        df = pd.DataFrame({"name": names}, columns=["name"])
        return ListSchemas.validate(df)

    def list_objects(self, schema_conf: SchemaConfig, schema_name: str) -> DataFrame[ListObjects]:
        named_objects = [
            *((name, "Table") for name in self._inspector.get_table_names(schema=schema_name)),
            *((name, "View") for name in self._inspector.get_view_names(schema=schema_name)),
        ]

        include = schema_conf._include.get(schema_name)
        exclude = schema_conf._exclude.get(schema_name)

        rows = []
        for name, object_type in named_objects:
            if include and name not in include:
                continue
            if exclude and name in exclude:
                continue

            rows.append({
                "object_name": name,
                "object_type": object_type,
                "object_description": self._get_comment(schema_name, name),
            })

        df = pd.DataFrame(rows, columns=["object_name", "object_type", "object_description"])
        return ListObjects.validate(df)

    def list_columns(self, schema_name: str, object_name: str) -> DataFrame[ListColumns]:
        columns = self._get_columns(schema_name, object_name)
        pk_columns = set(self._get_pk_columns(schema_name, object_name))
        unique_columns = self._get_single_column_uniques(schema_name, object_name)
        fk_map = self._get_column_fk_map(schema_name, object_name)

        rows = []
        for column in columns:
            facts = self._type_facts(column["type"])
            fk_ref = fk_map.get(column["name"])
            rows.append({
                "column_name": column["name"],
                "sql_type": facts.sql_type,
                "is_nullable": bool(column["nullable"]),
                "is_identity": column.get("identity") is not None,
                "is_computed": column.get("computed") is not None,
                "max_length": facts.max_length,
                "precision": facts.precision,
                "scale": facts.scale,
                "collation_name": facts.collation,
                "has_default": column.get("default") is not None,
                "default_value": column.get("default"),
                "is_unique": column["name"] in unique_columns,
                "is_primary_key": column["name"] in pk_columns,
                "is_foreign_key": fk_ref is not None,
                "fk_ref_schema": fk_ref[0] if fk_ref else None,
                "fk_ref_table": fk_ref[1] if fk_ref else None,
                "fk_ref_column": fk_ref[2] if fk_ref else None,
                "description": column.get("comment"),
            })

        df = pd.DataFrame(rows, columns=[
            "column_name", "sql_type", "is_nullable", "is_identity", "is_computed",
            "max_length", "precision", "scale", "collation_name", "has_default",
            "default_value", "is_unique", "is_primary_key", "is_foreign_key",
            "fk_ref_schema", "fk_ref_table", "fk_ref_column", "description",
        ])
        return ListColumns.validate(df)

    def list_unique_clusters(self, schema_name: str, object_name: str) -> DataFrame[ListUniqueClusters]:
        rows = []
        seen_clusters: set[tuple[frozenset[str], str | None]] = set()

        def add_cluster(key_name: str, columns: Sequence[str], *, is_primary_key: bool, is_unique_constraint: bool, index_type: str, filter_definition: str | None = None):
            cluster_key = (frozenset(columns), filter_definition)
            if cluster_key in seen_clusters:
                return
            if len(columns) <= 1 and filter_definition is None:
                return

            seen_clusters.add(cluster_key)
            rows.append({
                "key_name": key_name,
                "is_primary_key": is_primary_key,
                "is_unique_constraint": is_unique_constraint,
                "is_unique": True,
                "index_type": index_type,
                "column_count": len(columns),
                "columns": ", ".join(columns),
                "filter_definition": filter_definition,
            })

        pk = self._inspector.get_pk_constraint(object_name, schema=schema_name)
        if pk and pk.get("constrained_columns"):
            add_cluster(
                pk.get("name") or f"pk_{object_name}",
                pk["constrained_columns"],
                is_primary_key=True,
                is_unique_constraint=False,
                index_type="PRIMARY KEY",
            )

        for constraint in self._get_unique_constraints(schema_name, object_name):
            add_cluster(
                constraint.get("name") or f"uq_{object_name}",
                constraint["column_names"],
                is_primary_key=False,
                is_unique_constraint=True,
                index_type="UNIQUE CONSTRAINT",
            )

        for index in self._inspector.get_indexes(object_name, schema=schema_name):
            raw_names = index.get("column_names") or []
            column_names = [name for name in raw_names if name is not None]
            if not index.get("unique") or len(column_names) != len(raw_names):
                continue

            add_cluster(
                index.get("name") or f"ix_{object_name}",
                column_names,
                is_primary_key=False,
                is_unique_constraint=False,
                index_type="UNIQUE INDEX",
                filter_definition=self._index_filter(index),
            )

        df = pd.DataFrame(rows, columns=[
            "key_name", "is_primary_key", "is_unique_constraint", "is_unique",
            "index_type", "column_count", "columns", "filter_definition",
        ])
        return ListUniqueClusters.validate(df)

    def list_foreign_keys(self, schema_name: str, object_name: str) -> DataFrame[ListForeignKeys]:
        rows = []
        for fk in self._inspector.get_foreign_keys(object_name, schema=schema_name):
            options = fk.get("options") or {}
            rows.append({
                "fk_name": fk.get("name") or f"fk_{object_name}_{'_'.join(fk['constrained_columns'])}",
                "ref_schema": fk.get("referred_schema") or schema_name,
                "ref_table": fk["referred_table"],
                "columns": ", ".join(fk["constrained_columns"]),
                "ref_columns": ", ".join(fk["referred_columns"]),
                "on_delete": self._referential_action(options.get("ondelete")),
                "on_update": self._referential_action(options.get("onupdate")),
            })

        df = pd.DataFrame(rows, columns=[
            "fk_name", "ref_schema", "ref_table", "columns", "ref_columns",
            "on_delete", "on_update",
        ])
        return ListForeignKeys.validate(df)

    def list_check_constraints(self, schema_name: str, object_name: str) -> DataFrame[ListCheckConstraints]:
        checks = self._get_check_constraints(schema_name, object_name)
        column_names = [column["name"] for column in self._get_columns(schema_name, object_name)]

        rows = []
        for index, check in enumerate(checks):
            definition = check["sqltext"]
            rows.append({
                "check_name": check.get("name") or f"ck_{object_name}_{index}",
                "definition": definition,
                "column_name": self._attribute_check_column(definition, column_names),
            })

        df = pd.DataFrame(rows, columns=["check_name", "definition", "column_name"])
        return ListCheckConstraints.validate(df)

    def list_procedures(self, schema_conf: SchemaConfig, schema_name: str) -> DataFrame[ListProcedures]:
        include = schema_conf._include.get(schema_name)
        exclude = schema_conf._exclude.get(schema_name)

        rows = []
        for name in self._reflect_procedure_names(schema_name):
            if include and name not in include:
                continue
            if exclude and name in exclude:
                continue

            rows.append({
                "procedure_name": name,
                "procedure_description": None,
            })

        df = pd.DataFrame(rows, columns=["procedure_name", "procedure_description"])
        return ListProcedures.validate(df)

    def list_parameters(self, schema_name: str, procedure_name: str) -> DataFrame[ListParameters]:
        rows = []
        for parameter in self._reflect_parameters(schema_name, procedure_name):
            rows.append({
                "parameter_name": parameter["name"],
                "sql_type": parameter["sql_type"],
                "is_nullable": parameter["is_nullable"],
                "mode": parameter["mode"],
                "ordinal": parameter["ordinal"],
            })

        df = pd.DataFrame(rows, columns=[
            "parameter_name", "sql_type", "is_nullable", "mode", "ordinal",
        ])
        return ListParameters.validate(df)

    def _reflect_procedure_names(self, schema_name: str) -> list[str]:
        if self._dialect not in _INFO_SCHEMA_ROUTINE_DIALECTS:
            return []

        sql = SQL(
            raw_query=(
                "SELECT routine_name FROM information_schema.routines"
                " WHERE routine_schema = :schema_name AND routine_type = 'PROCEDURE'"
            ),
            query_parameters={"schema_name": schema_name},
        )
        _, data = self._handler.run_sql(sql)
        if data.empty:
            return []
        return [str(name) for name in data.iloc[:, 0].tolist()]

    def _reflect_parameters(self, schema_name: str, procedure_name: str) -> list[dict[str, Any]]:
        if self._dialect not in _INFO_SCHEMA_ROUTINE_DIALECTS:
            return []

        sql = SQL(
            raw_query=(
                "SELECT parameter_name, data_type, ordinal_position, parameter_mode"
                " FROM information_schema.parameters"
                " WHERE specific_schema = :schema_name AND specific_name = :procedure_name"
                " AND parameter_name IS NOT NULL"
                " ORDER BY ordinal_position"
            ),
            query_parameters={"schema_name": schema_name, "procedure_name": procedure_name},
        )
        _, data = self._handler.run_sql(sql)

        return [
            {
                "name": str(row.parameter_name),
                "sql_type": str(row.data_type),
                "is_nullable": False,
                "mode": (str(row.parameter_mode) or "IN").upper(),
                "ordinal": row.ordinal_position,
            }
            for row in data.itertuples(index=False)
        ]

    def _is_system_schema(self, name: str) -> bool:
        lowered = name.lower()

        if lowered in _SYSTEM_SCHEMAS.get(self._dialect, frozenset()):
            return True

        return lowered.startswith(_SYSTEM_SCHEMA_PREFIXES.get(self._dialect, ()))

    def _get_comment(self, schema_name: str, object_name: str) -> str | None:
        try:
            return self._inspector.get_table_comment(object_name, schema=schema_name).get("text")
        except (NotImplementedError, NoSuchTableError):
            return None

    def _get_columns(self, schema_name: str, object_name: str) -> list[dict[str, Any]]:
        key = (schema_name, object_name)
        if key not in self._columns_cache:
            reflected = self._inspector.get_columns(object_name, schema=schema_name)
            self._columns_cache[key] = [dict(column) for column in reflected]
        return self._columns_cache[key]

    def _get_pk_columns(self, schema_name: str, object_name: str) -> list[str]:
        pk = self._inspector.get_pk_constraint(object_name, schema=schema_name)
        return list(pk.get("constrained_columns") or []) if pk else []

    def _get_unique_constraints(self, schema_name: str, object_name: str) -> list[ReflectedUniqueConstraint]:
        try:
            return self._inspector.get_unique_constraints(object_name, schema=schema_name)
        except NotImplementedError:
            return self._unique_constraints_fallback(schema_name, object_name)

    def _unique_constraints_fallback(self, schema_name: str, object_name: str) -> list[ReflectedUniqueConstraint]:
        data = self._run_fallback_sql(_UNIQUE_CONSTRAINTS_FALLBACK_SQL, schema_name, object_name)
        if data is None:
            return []

        grouped: dict[str, list[str]] = {}
        for row in data.itertuples(index=False):
            grouped.setdefault(str(row.constraint_name), []).append(str(row.column_name))

        return [
            ReflectedUniqueConstraint(
                name=name,
                column_names=columns,
                comment=None,
                duplicates_index=None,
                dialect_options={},
            )
            for name, columns in grouped.items()
        ]

    def _get_check_constraints(self, schema_name: str, object_name: str) -> list[ReflectedCheckConstraint]:
        try:
            return self._inspector.get_check_constraints(object_name, schema=schema_name)
        except NotImplementedError:
            return self._check_constraints_fallback(schema_name, object_name)

    def _check_constraints_fallback(self, schema_name: str, object_name: str) -> list[ReflectedCheckConstraint]:
        data = self._run_fallback_sql(_CHECK_CONSTRAINTS_FALLBACK_SQL, schema_name, object_name)
        if data is None:
            return []

        return [
            ReflectedCheckConstraint(
                name=str(row.constraint_name),
                sqltext=str(row.sqltext),
                comment=None,
                dialect_options={},
            )
            for row in data.itertuples(index=False)
        ]

    def _run_fallback_sql(self, sql_names: Mapping[DialectTypes, str], schema_name: str, object_name: str) -> pd.DataFrame | None:
        sql_name = sql_names.get(self._dialect)
        if sql_name is None:
            return None

        sql = SQL(
            sql_path=sql_name,
            query_parameters={"schema_name": schema_name, "object_name": object_name},
        )
        sql.set_script_dir(_FALLBACK_SQL_DIR)

        _, data = self._handler.run_sql(sql)
        return data

    def _get_single_column_uniques(self, schema_name: str, object_name: str) -> set[str]:
        unique_columns: set[str] = set()

        for constraint in self._get_unique_constraints(schema_name, object_name):
            if len(constraint["column_names"]) == 1:
                unique_columns.add(constraint["column_names"][0])

        for index in self._inspector.get_indexes(object_name, schema=schema_name):
            column_names = index.get("column_names") or []
            if (
                index.get("unique")
                and self._index_filter(index) is None
                and len(column_names) == 1
                and column_names[0] is not None
            ):
                unique_columns.add(column_names[0])

        return unique_columns

    def _get_column_fk_map(self, schema_name: str, object_name: str) -> dict[str, tuple[str, str, str]]:
        fk_map: dict[str, tuple[str, str, str]] = {}
        for fk in self._inspector.get_foreign_keys(object_name, schema=schema_name):
            ref_schema = fk.get("referred_schema") or schema_name
            for column, ref_column in zip(fk["constrained_columns"], fk["referred_columns"]):
                fk_map[column] = (ref_schema, fk["referred_table"], ref_column)
        return fk_map

    def _type_facts(self, sa_type: Any) -> ReflectedTypeFacts:
        try:
            dialect_map = get_map(self._dialect)
        except ValueError:
            return DialectMap.reflected_type_facts(sa_type)
        return dialect_map.reflected_type_facts(sa_type)

    @staticmethod
    def _index_filter(index: Mapping[str, Any]) -> str | None:
        options = index.get("dialect_options") or {}
        for key, value in options.items():
            if key.endswith("_where") and value is not None:
                return str(value)
        return None

    @staticmethod
    def _referential_action(action: str | None) -> str:
        return (action or "NO ACTION").strip().upper().replace(" ", "_")

    @staticmethod
    def _attribute_check_column(definition: str, column_names: list[str]) -> str | None:
        referenced = [
            name for name in column_names
            if re.search(rf"(?<![0-9A-Za-z_]){re.escape(name)}(?![0-9A-Za-z_])", definition, re.IGNORECASE)
        ]
        return referenced[0] if len(referenced) == 1 else None
