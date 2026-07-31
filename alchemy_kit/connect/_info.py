import random
import string
from pathlib import Path
from typing import Any

import sqlalchemy

from ..types.dialect_types import DialectTypes
from ..resources.dialect_map import DialectMap
from ..resources.dir_helpers import find_project_root


class ConnectionInfo[_TypeParameters: str]:
    """Holds the details needed to connect and to locate SQL scripts.

    Pairs a SQLAlchemy URL with a stable identifier and the directory used to
    resolve file-based queries. The ``unique_id`` is taken from the caller when
    provided, otherwise a random 32-character one is generated. The script
    directory is resolved lazily (see ``get_script_dir``) and can be overridden
    explicitly with ``set_script_dir``.

    The dialect is derived from the URL's backend name, so it always stays in
    sync with ``con_url``. Passing ``expect`` additionally pins the dialect's
    SQL type names (``_TypeParameters``) onto the connection, which is what
    gives the units built from it a checked ``cast``.

    Attributes:
        con_url: The SQLAlchemy URL used to build engines for this connection.
        unique_id: Stable identifier for the connection, used to key engines.
        dialect: The database dialect, derived from ``con_url``.
        script_dir: Base directory for resolving SQL files; ``None`` until
            resolved or set.
    """

    def __init__(
        self,
        conn_url: sqlalchemy.URL,
        unique_id: str | None = None,
        *,
        expect: type[DialectMap[_TypeParameters]] | None = None,
    ) -> None:
        self.script_dir: Path | None = None
        self.con_url = conn_url
        self.dialect = self._resolve_dialect(conn_url)
        self.expect_dialect(expect)

        if isinstance(unique_id, str):
            self.unique_id = unique_id
        else:
            self.unique_id = ''.join(random.choices(string.ascii_letters + string.digits, k=32))

    def expect_dialect(self, expect: "type[DialectMap[Any]] | None") -> None:
        """Reject a connection whose dialect is not the expected one.

        Args:
            expect: The dialect map the caller asked for; ``None`` skips the
                check.

        Raises:
            ValueError: If the URL resolves to a different dialect.
        """
        if expect is not None and expect.dialect is not self.dialect:
            raise ValueError(
                f"Expected a {expect.dialect} connection, but '{self.con_url}'"
                f" is {self.dialect}"
            )

    @staticmethod
    def _resolve_dialect(conn_url: sqlalchemy.URL) -> DialectTypes:
        backend = conn_url.get_backend_name()
        try:
            return DialectTypes(backend)
        except ValueError:
            raise ValueError(f"Unsupported dialect '{backend}' for URL: {conn_url}")

    def engine_kwargs(self) -> dict[str, Any]:
        """Return the ``create_engine`` options this connection needs beyond
        its URL.

        pyodbc otherwise sends an execute-many one round trip per row, so
        ``fast_executemany`` is turned on to bind the records as parameter
        arrays instead; the other drivers already batch natively. An empty
        driver name means SQLAlchemy's default, which is pyodbc for MSSQL.
        """
        if self.dialect is DialectTypes.MSSQL and self.con_url.get_driver_name() in ("", "pyodbc"):
            return {"fast_executemany": True}

        return {}

    def get_script_dir(self) -> Path:
        """Return the SQL script directory, resolving and caching it on first use.

        If ``script_dir`` has already been set (via ``set_script_dir`` or a
        previous call), it is returned as-is. Otherwise it is discovered with
        ``find_script_dir``, cached on the instance, and returned.
        """
        if self.script_dir is None:
            self.script_dir = self.find_script_dir()
            return self.script_dir

        return self.script_dir

    @staticmethod
    def find_script_dir(folder_name: str = "sql_script") -> Path:
        """Locate the SQL script folder inside the caller's project.

        Determines the caller (the first stack frame outside the alchemy_kit
        package), walks up to its project root (the first ancestor holding one
        of ``Settings.project_markers``), and finds ``folder_name`` there: directly under
        the root if present, otherwise the first matching directory found by
        recursive search.

        Args:
            folder_name: Name of the directory holding the SQL scripts.

        Returns:
            The resolved path to the ``folder_name`` directory.

        Raises:
            ValueError: If the caller, the project root, or ``folder_name``
                cannot be found.
        """
        project_root = find_project_root()

        # Locate `folder_name` within the caller's project.
        candidate = project_root / folder_name
        if candidate.is_dir():
            return candidate

        for nested in project_root.rglob(folder_name):
            if nested.is_dir():
                return nested

        raise ValueError(f"Could not find a '{folder_name}' directory in {project_root}")

    def set_script_dir(self, script_dir: Path):
        """Override the SQL script directory with an explicit path.

        Use this to bypass ``find_script_dir`` auto-discovery and point at a
        known directory. Raises if the path is not an existing directory.

        Args:
            script_dir: Path to an existing directory holding the SQL scripts.

        Raises:
            ValueError: If ``script_dir`` is not an existing directory.
        """
        if not script_dir.is_dir():
            raise ValueError(f"Directory do not exists: {script_dir}")

        self.script_dir = script_dir

