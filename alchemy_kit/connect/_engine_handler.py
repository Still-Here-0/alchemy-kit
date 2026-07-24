from collections.abc import Mapping, Sequence
from typing import Literal, Protocol, cast

import pandas as pd
import sqlalchemy

from ..resources._sql import SQL
from ..types._sql_parameters import SqlParamMap
from ..types.sql_types import SQL_EXPAND_CLASSES
from ._info import ConnectionInfo


class _UnitFactory[_UnitT](Protocol):
    def _get_unit(self, handler: "EngineHandler") -> _UnitT: ...


class EngineHandler:
    """Performs database operations against a single pooled engine.

    Binds a SQLAlchemy engine to its ``ConnectionInfo`` and serves as the entry
    point for interacting with that database.

    Handlers are created by ``EngineManager`` rather than directly; several
    handlers may share one pooled engine, and the manager detaches them
    (clearing ``_engine``) when its ``with`` block exits, after which the
    handler can no longer be used.
    """

    def __init__(self, engine: sqlalchemy.Engine, con_info: ConnectionInfo) -> None:
        self._engine = engine
        self._con_info = con_info

    def get_unit[_UnitT](self, model: _UnitFactory[_UnitT]) -> _UnitT:
        """Return a unit for ``model``, bound to this handler's connection and
        compiled with its dialect."""
        return model._get_unit(self)

    def get_inspector(self) -> sqlalchemy.Inspector:
        """Return a SQLAlchemy ``Inspector`` bound to this handler's engine."""
        return sqlalchemy.inspect(self._engine)

    def quote_identifier(self, identifier: str) -> str:
        """Quote a schema/table/column name using this engine's dialect rules."""
        return self._engine.dialect.identifier_preparer.quote(identifier)

    def run_sql(self, sql: SQL) -> tuple[int | None, pd.DataFrame]:
        """Run one statement on its own connection and return its
        ``(row_count, DataFrame)`` pair; ``f_check`` gates commit vs
        rollback (``(None, empty)`` on rollback)."""
        with self._engine.connect() as conn:
            result = self._execute_sql(conn, sql)

            if not sql.f_check(conn):
                conn.rollback()
                return None, pd.DataFrame()

            row_count, data = self._collect_result(result)
            conn.commit()
            return row_count, data

    def run_sqls(self, sqls: Sequence[SQL]) -> list[tuple[int | None, pd.DataFrame]]:
        """Run statements in order on one connection, in a single
        all-or-nothing transaction, returning one ``(row_count, DataFrame)``
        pair per statement.

        The shared connection keeps session state (e.g. temporary tables)
        alive across statements; the first failing ``f_check`` rolls back
        everything.
        """
        results: list[tuple[int | None, pd.DataFrame]] = []

        with self._engine.connect() as conn:
            for sql in sqls:
                result = self._execute_sql(conn, sql)

                if not sql.f_check(conn):
                    conn.rollback()
                    return [(None, pd.DataFrame()) for _ in range(len(results) + 1)]

                results.append(self._collect_result(result))

            conn.commit()

        return results

    def _execute_sql(self, conn: sqlalchemy.Connection, sql: SQL) -> sqlalchemy.CursorResult:
        if sql.script_dir is None and sql.sql_path is not None:
            sql.set_script_dir(self._con_info.get_script_dir())

        sql.process_query()
        query = sqlalchemy.text(cast(str, sql.processed_query))

        if isinstance(sql.query_parameters, Mapping):
            return self._execute_with_binded_parameters(conn, query, sql.query_parameters)

        return conn.execute(query, sql.query_parameters)

    @staticmethod
    def _collect_result(result: sqlalchemy.CursorResult) -> tuple[int | None, pd.DataFrame]:
        data = pd.DataFrame()
        if result.returns_rows:
            data = pd.DataFrame(result.fetchall(), columns=list(result.keys()))
        return result.rowcount, data

    def _execute_with_binded_parameters(self, conn: sqlalchemy.Connection, query: sqlalchemy.TextClause, parameters: SqlParamMap) -> sqlalchemy.CursorResult:
        binds = [
            sqlalchemy.bindparam(key, value, expanding=isinstance(value, SQL_EXPAND_CLASSES))
            for key, value in parameters.items()
        ]

        binded_query = query.bindparams(*binds) if binds else query

        return conn.execute(binded_query)
    
    def insert_data(
        self,
        data: pd.DataFrame,
        database_name: str,
        table_name: str,
        schema_name: str,
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
