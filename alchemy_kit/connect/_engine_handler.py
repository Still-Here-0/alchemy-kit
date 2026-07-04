from typing import Sequence, cast

import pandas as pd
import sqlalchemy

from ..resources._sql import SQL
from ..types._sql_parameters import SqlParamMap
from ..types.sql_types import SqlExpandType
from ._info import ConnectionInfo


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

    def run_sql(self, sql: SQL) -> tuple[int | None, pd.DataFrame]:
        """Run any query and return both the affected row count and the result rows.

        If the ``SQL`` has no ``script_dir`` of its own, it is assigned this
        connection's script directory (resolved via ``ConnectionInfo.get_script_dir``)
        so that file-based queries resolve against the caller's project; a
        ``script_dir`` already set on the ``SQL`` is left untouched.

        Processes the ``SQL`` (loading from file or raw text, converting
        ``@param`` placeholders to ``:param`` and applying text replacements),
        then executes it on a fresh connection. When ``query_parameters`` is a
        sequence it is passed straight through (executemany-style); otherwise
        each parameter is bound individually, expanding ``SqlExpandType`` values
        into ``IN`` lists.

        The statement runs inside a transaction gated by ``sql.f_check``: when
        it returns True the transaction commits, otherwise it rolls back. On
        commit the row count is captured and, for row-returning statements
        (SELECT, OUTPUT, SELECT SCOPE_IDENTITY(), ...), the rows are loaded into
        the DataFrame; non-row-returning statements (UPDATE, DELETE, TRUNCATE,
        ...) yield an empty DataFrame.

        Returns:
            A ``(row_count, DataFrame)`` pair. When ``f_check`` returns False
            (rollback) the row count is ``None`` and the DataFrame is empty.
        """
        if sql.script_dir is None:
            sql.set_script_dir(self._con_info.get_script_dir())

        sql.process_query()
        query = sqlalchemy.text(cast(str, sql.processed_query))
        row_count = None
        data = pd.DataFrame()

        with self._engine.connect() as conn:
            if isinstance(sql.query_parameters, Sequence):
                result = conn.execute(query, sql.query_parameters)
            else:
                result = self._bind_parameters(conn, query, sql.query_parameters)

            if sql.f_check(conn):
                row_count = result.rowcount
                if result.returns_rows:
                    data = pd.DataFrame(result.fetchall(), columns=list(result.keys()))
                conn.commit()
            else:
                conn.rollback()

            return row_count, data

    def _bind_parameters(self, conn: sqlalchemy.Connection, query: sqlalchemy.TextClause, parameters: SqlParamMap) -> sqlalchemy.CursorResult:
        binds = [
            sqlalchemy.bindparam(key, value, expanding=isinstance(value, SqlExpandType))
            for key, value in parameters.items()
        ]

        binded_query = query.bindparams(*binds) if binds else query

        return conn.execute(binded_query)
    
    def insert_data(
        self,
        data: pd.DataFrame,
        table_name: str,
        schema_name: str,
        *,
        truncate: bool = False,
    ): # TODO: validate it after builder is implemented
        ...

