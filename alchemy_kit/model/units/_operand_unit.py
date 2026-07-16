from typing import Any

import sqlalchemy as sa
from sqlalchemy.sql import sqltypes

from ...resources._compiler import new_sql_type
from ...types.dialect_types import DialectTypes
from ._column_unit import AggregateColumnUnit, ColumnUnit, WindowFunctionUnit

_CurrentDate = new_sql_type("_CurrentDate", "CURRENT_DATE", sqltypes.Date(), unsupported=(DialectTypes.MSSQL,))
_CurrentTime = new_sql_type(
    "_CurrentTime", "CURRENT_TIME", sqltypes.Time(), unsupported=(DialectTypes.MSSQL, DialectTypes.ORACLE)
)
_CurrentUser = new_sql_type(
    "_CurrentUser",
    "CURRENT_USER",
    sqltypes.String(),
    unsupported=(DialectTypes.SQLITE,),
    overrides={DialectTypes.ORACLE: "USER"},
)
_SessionUser = new_sql_type(
    "_SessionUser",
    "SESSION_USER",
    sqltypes.String(),
    unsupported=(DialectTypes.SQLITE, DialectTypes.ORACLE),
    overrides={DialectTypes.MYSQL: "SESSION_USER()", DialectTypes.MARIADB: "SESSION_USER()"},
)


class OperandUnit:
    """Context-free SQL functions that take neither a column nor an object — only
    the surrounding query gives them meaning. Spawned as statics, not bound to any
    model."""

    @staticmethod
    def row_number() -> WindowFunctionUnit[Any]:
        """Return ``ROW_NUMBER()`` — rows numbered from 1 within their window
        (needs ``over``, typically with ``order_by``)."""
        return WindowFunctionUnit[Any](sa.func.row_number())

    @staticmethod
    def rank() -> WindowFunctionUnit[Any]:
        """Return ``RANK()`` — like row numbers, but tied rows share a rank and
        leave gaps after them (needs ``over`` with ``order_by``)."""
        return WindowFunctionUnit[Any](sa.func.rank())

    @staticmethod
    def dense_rank() -> WindowFunctionUnit[Any]:
        """Return ``DENSE_RANK()`` — like row numbers, but tied rows share a rank
        without leaving gaps (needs ``over`` with ``order_by``)."""
        return WindowFunctionUnit[Any](sa.func.dense_rank())

    @staticmethod
    def ntile(buckets: int) -> WindowFunctionUnit[Any]:
        """Return ``NTILE(buckets)`` — the window's rows split into ``buckets``
        ranked groups (needs ``over`` with ``order_by``)."""
        return WindowFunctionUnit[Any](sa.func.ntile(buckets))

    @staticmethod
    def percent_rank() -> WindowFunctionUnit[Any]:
        """Return ``PERCENT_RANK()`` — each row's relative rank in ``[0, 1]``
        (needs ``over`` with ``order_by``)."""
        return WindowFunctionUnit[Any](sa.func.percent_rank())

    @staticmethod
    def cume_dist() -> WindowFunctionUnit[Any]:
        """Return ``CUME_DIST()`` — the cumulative distribution in ``(0, 1]``
        (needs ``over`` with ``order_by``)."""
        return WindowFunctionUnit[Any](sa.func.cume_dist())

    @staticmethod
    def count() -> AggregateColumnUnit[Any]:
        """Return ``COUNT(*)`` — the row count; usable as a plain aggregate or
        windowed with ``over``."""
        return AggregateColumnUnit[Any](sa.func.count())

    @staticmethod
    def current_timestamp() -> ColumnUnit[Any]:
        """Return ``CURRENT_TIMESTAMP`` — the current date and time."""
        return ColumnUnit[Any](sa.func.current_timestamp())

    @staticmethod
    def current_date() -> ColumnUnit[Any]:
        """Return ``CURRENT_DATE`` — the current date. Unsupported: MSSQL."""
        return ColumnUnit[Any](_CurrentDate())

    @staticmethod
    def current_time() -> ColumnUnit[Any]:
        """Return ``CURRENT_TIME`` — the current time. Unsupported: MSSQL, Oracle."""
        return ColumnUnit[Any](_CurrentTime())

    @staticmethod
    def current_user() -> ColumnUnit[Any]:
        """Return ``CURRENT_USER`` — the current user (``USER`` on Oracle).
        Unsupported: SQLite."""
        return ColumnUnit[Any](_CurrentUser())

    @staticmethod
    def session_user() -> ColumnUnit[Any]:
        """Return ``SESSION_USER`` — the session user. Unsupported: SQLite,
        Oracle."""
        return ColumnUnit[Any](_SessionUser())
