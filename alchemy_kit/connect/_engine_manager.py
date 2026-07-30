from contextlib import AbstractContextManager
from logging import Logger
from types import TracebackType
from typing import Optional, Self, NamedTuple, TypeAlias

import sqlalchemy

from ..resources._better_logger import BetterLogger
from ._engine_handler import EngineHandler
from ._info import ConnectionInfo

class _EngineInfo(NamedTuple):
    engine: sqlalchemy.Engine
    con_info: ConnectionInfo
    handlers: list[EngineHandler]

_EnginePool: TypeAlias = dict[str, _EngineInfo]

class EngineManager(AbstractContextManager):
    """Context manager that owns a pool of SQLAlchemy engines.

    Each connection is created once, keyed by its ``ConnectionInfo.unique_id``,
    and reused for every handler built from it. Use it as a context manager:

    ```
        with EngineManager(logger) as manager:
            handler = manager.create_engine(con_info)
            handler.run_sql(...)
    ```

    The pool is only initialised on entering the ``with`` block; calling the
    methods outside one has no engine pool to work with. On exit every pooled
    engine is disposed and its handlers are detached (their engine reference is
    cleared so they can no longer run queries); disposal errors are collected
    per connection so one failure does not stop the rest being cleaned up.

    The ``logger`` passed to the constructor is used as-is if it is already a
    ``BetterLogger``, otherwise (a standard ``Logger`` or ``None``) it is
    wrapped in one.

    Attributes:
        logger: Logger used for manager events; wrapped in a ``BetterLogger``.
    """

    def __init__(self, logger: Optional[BetterLogger | Logger]) -> None:
        self._engine_pool: _EnginePool
        self.logger: BetterLogger

        if isinstance(logger, BetterLogger):
            self.logger = logger
        else:
            self.logger = BetterLogger(logger)

    def __enter__(self) -> Self:
        self._engine_pool = {}
        return self

    def __exit__(self, _exc_type: type[BaseException] | None, _exc_value: BaseException | None, _traceback: TracebackType | None, /) -> None:  # pyright: ignore[reportUnusedParameter]
        log_errors: list[tuple[str, Exception]] = []
        for key, pool in self._engine_pool.items():
            try:
                pool.engine.dispose()
            except Exception as ex:
                log_errors.append((key, ex))

            for handler in pool.handlers:
                handler._engine = None # type: ignore

        if log_errors:
            pass # TODO: log errors to terminal

        self._engine_pool.clear()

    def create_handler(self, con_info: ConnectionInfo) -> EngineHandler:
        """Create and pool a new engine for a connection, returning a handler.

        Builds a SQLAlchemy engine from ``con_info.con_url``, stores it in the
        pool keyed by ``con_info.unique_id``, and returns a handler bound to it.

        Args:
            con_info: The connection to build an engine for.

        Returns:
            An ``EngineHandler`` for running queries against the new engine.

        Raises:
            ValueError: If an engine with the same ``unique_id`` already exists.
        """
        if self.handler_exists(con_info.unique_id):
            raise ValueError(f"Engine with unique id '{con_info.unique_id}' aready exists")

        engine = sqlalchemy.create_engine(con_info.con_url, **con_info.engine_kwargs())
        self._engine_pool[con_info.unique_id] = _EngineInfo(engine, con_info, [])

        return self.get_handler(con_info.unique_id)

    def get_handler(self, key: str) -> EngineHandler:
        """Build an additional handler for an already-pooled engine.

        Each call returns a new handler sharing the pooled engine; the handler
        is tracked so it can be detached when the manager exits.

        Args:
            key: The ``unique_id`` of an existing pooled engine.

        Returns:
            A new ``EngineHandler`` bound to the pooled engine.

        Raises:
            KeyError: If no engine exists for ``key``.
        """
        info = self._engine_pool[key]
        new_handler = EngineHandler(info.engine, info.con_info)
        info.handlers.append(new_handler)
        return new_handler

    def handler_exists(self, key: str) -> bool:
        """Return whether an engine is pooled under the given ``unique_id``.

        Args:
            key: The ``unique_id`` to look up.

        Returns:
            ``True`` if an engine exists for ``key``, otherwise ``False``.
        """
        return key in self._engine_pool.keys()

