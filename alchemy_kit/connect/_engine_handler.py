from collections.abc import Mapping, Sequence
from typing import Any, Literal, Protocol, cast

import pandas as pd
import sqlalchemy

from ..resources._sql import SQL
from ..types._sql_parameters import SqlParamMap
from ..types.sql_types import SQL_EXPAND_CLASSES, SqlParamType
from ._info import ConnectionInfo


class _UnitFactory[_TypeParameters: str, _UnitT](Protocol):
    def _get_unit(self, handler: "EngineHandler[_TypeParameters]") -> _UnitT: ...


class EngineHandler[_TypeParameters: str]:
    """Performs database operations against a single pooled engine.

    Binds a SQLAlchemy engine to its ``ConnectionInfo`` and serves as the entry
    point for interacting with that database.

    Handlers are created by ``EngineManager`` rather than directly; several
    handlers may share one pooled engine, and the manager detaches them
    (clearing ``_engine``) when its ``with`` block exits, after which the
    handler can no longer be used.
    """

    def __init__(self, engine: sqlalchemy.Engine, con_info: ConnectionInfo[_TypeParameters]) -> None:
        self._engine = engine
        self._con_info = con_info

    def get_unit[_UnitT](self, model: _UnitFactory[_TypeParameters, _UnitT]) -> _UnitT:
        """Return a unit for ``model``, bound to this handler's connection and
        compiled with its dialect."""
        return model._get_unit(self)

    def get_connection_info(self) -> ConnectionInfo[_TypeParameters]:
        """Return the current ``ConnectionInfo`` used by the handler"""
        return self._con_info

    def get_inspector(self) -> sqlalchemy.Inspector:
        """Return a SQLAlchemy ``Inspector`` bound to this handler's engine.

        Reads the database's schema rather than its rows. Rarely needed
        directly: this is how the package reflects a database into the
        generated models (``model.build``).
        """
        return sqlalchemy.inspect(self._engine)

    def quote_identifier(self, identifier: str) -> str:
        """Quote a schema/table/column name with this connection's dialect
        delimiters.

        For naming an object inside a hand-written ``SQL`` query, where the
        name is text rather than a bound parameter.
        """
        return self._con_info.dialect.quote_identifier(identifier)

    def run_sql(self, sql: SQL) -> tuple[int | None, pd.DataFrame]:
        """Run one statement on its own connection and return its
        ``(row_count, DataFrame)`` pair; ``f_check`` gates commit vs
        rollback (``(None, empty)`` on rollback).

        A statement bound to an empty record list executes zero times and is
        reported as ``(0, empty)``."""
        with self._engine.connect() as conn:
            result = self._execute_sql(conn, sql)

            if not sql.f_check(conn):
                conn.rollback()
                return None, pd.DataFrame()

            row_count, data = self._collect_result(result, sql)
            conn.commit()
            return row_count, data

    def run_sqls(self, sqls: Sequence[SQL]) -> list[tuple[int | None, pd.DataFrame]]:
        """Run statements in order on one connection, in a single
        all-or-nothing transaction, returning one ``(row_count, DataFrame)``
        pair per statement.

        The shared connection keeps session state (e.g. temporary tables)
        alive across statements; the first failing ``f_check`` rolls back
        everything. A statement bound to an empty record list executes zero
        times and is reported as ``(0, empty)`` without leaving the batch.
        """
        results: list[tuple[int | None, pd.DataFrame]] = []

        with self._engine.connect() as conn:
            for sql in sqls:
                result = self._execute_sql(conn, sql)

                if not sql.f_check(conn):
                    conn.rollback()
                    return [(None, pd.DataFrame()) for _ in range(len(results) + 1)]

                results.append(self._collect_result(result, sql))

            conn.commit()

        return results

    def _execute_sql(self, conn: sqlalchemy.Connection, sql: SQL) -> sqlalchemy.CursorResult | None:
        """Execute ``sql``, or return ``None`` when it binds an empty record
        list and therefore executes zero times."""
        if sql.script_dir is None and sql.sql_path is not None:
            sql.set_script_dir(self._con_info.get_script_dir())

        sql.process_query()
        query = sqlalchemy.text(cast(str, sql.processed_query))

        if isinstance(sql.query_parameters, Mapping):
            return self._execute_with_binded_parameters(conn, query, sql.query_parameters)

        if not sql.query_parameters:
            return None

        return self._execute_with_binded_records(conn, query, sql.query_parameters)

    @staticmethod
    def _collect_result(result: sqlalchemy.CursorResult | None, sql: SQL) -> tuple[int | None, pd.DataFrame]:
        """Collect ``(row_count, DataFrame)`` from an execution.

        A driver batching an execute-many often reports no row count at all
        (pyodbc's ``fast_executemany`` returns ``-1``); the number of records
        sent is reported instead, since the statement ran once per record.
        """
        if result is None:
            return 0, pd.DataFrame()

        data = pd.DataFrame()
        if result.returns_rows:
            data = pd.DataFrame(result.fetchall(), columns=list(result.keys()))

        row_count = result.rowcount
        if row_count is not None and row_count < 0 and not isinstance(sql.query_parameters, Mapping):
            row_count = len(sql.query_parameters)

        return row_count, data

    def _execute_with_binded_parameters(self, conn: sqlalchemy.Connection, query: sqlalchemy.TextClause, parameters: SqlParamMap) -> sqlalchemy.CursorResult:
        binds = [self._bind_parameter(key, value) for key, value in parameters.items()]
        binded_query = query.bindparams(*binds) if binds else query

        return conn.execute(binded_query)

    @staticmethod
    def _bind_parameter(key: str, value: SqlParamType) -> sqlalchemy.BindParameter[Any]:
        """Bind one parameter, expanding a collection into an ``IN`` list; a
        frozenset is copied into a tuple because SQLAlchemy indexes the value."""
        if isinstance(value, SQL_EXPAND_CLASSES):
            return sqlalchemy.bindparam(key, tuple(value), expanding=True)

        return sqlalchemy.bindparam(key, value)

    def _execute_with_binded_records(self, conn: sqlalchemy.Connection, query: sqlalchemy.TextClause, records: Sequence[SqlParamMap]) -> sqlalchemy.CursorResult:
        """Execute the statement once per record.

        Binds are never expanding here: SQLAlchemy rejects expanding parameters
        under execute-many, and a collection in a record is array data for one
        column rather than an ``IN`` list.
        """
        binds = [
            sqlalchemy.bindparam(key, value)
            for key, value in self._record_bind_values(records).items()
        ]
        binded_query = query.bindparams(*binds) if binds else query

        return conn.execute(binded_query, list(records))

    @staticmethod
    def _record_bind_values(records: Sequence[SqlParamMap]) -> dict[str, SqlParamType]:
        """Pick the value each key is typed from — the first non-null one any
        record holds — so execute-many binds are typed the way a single
        mapping's are."""
        keys = set(records[0])
        found: dict[str, SqlParamType] = {}

        for record in records:
            for key, value in record.items():
                if value is not None and key not in found:
                    found[key] = value

            if len(found) == len(keys):
                break

        return {key: found.get(key) for key in records[0]}

    def insert_data(
        self,
        data: pd.DataFrame,
        database_name: str,
        schema_name: str,
        table_name: str,
        *,
        truncate: bool = False,
        if_exists: Literal["fail", "replace", "append", "delete_rows"] = "append"
    ) -> int | None:
        """Bulk-insert a DataFrame into ``database.schema.table`` with pandas
        ``to_sql`` (``if_exists`` passed through, index never inserted) and
        return the inserted row count.

        ``truncate`` empties the table first, in the same transaction as the
        insert.
        """
        table_ref = f"{database_name}.{schema_name}.{table_name}"

        with self._engine.begin() as conn:
            if truncate:
                conn.execute(sqlalchemy.text(f"TRUNCATE TABLE {table_ref}"))

            return data.to_sql(table_name, conn, schema=schema_name, if_exists=if_exists, index=False)
