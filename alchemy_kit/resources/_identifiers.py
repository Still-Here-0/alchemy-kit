import builtins
import keyword
import re


class Identifiers:
    """Owns the set of names already used in one generated namespace and hands
    out unique, valid Python identifiers and filesystem-safe file/folder names.

    Each instance is seeded with Python keywords, builtins, and the names the
    generated templates rely on, so a derived name never shadows them. Create
    one instance per namespace (e.g. one for a module's attributes, one for a
    package's object names).
    """

    # Python keywords, builtins, and names the generated templates depend on.
    _RESERVED_PY_NAMES: frozenset[str] = frozenset(
        set(keyword.kwlist) | set(keyword.softkwlist) | set(dir(builtins)) | {
            # method receiver
            "self",

            # base model
            "get_unit", "Meta", "Config", "BaseModel", "validate",
            "strip_timezone",

            # imports
            "Optional", "Any", "Decimal", "pa",  "init", "date",
            "Series", "datetime", "SQL", "DataFrame",
            "CallableModel", "CallableUnit", "EngineHandler",

            # object unit
            "get_metadata", "set_alias",

            # callable unit
            "run", "to_sql", "render",
        }
    )

    # Windows reserves these device names regardless of extension.
    _RESERVED_FILE_NAMES: frozenset[str] = frozenset({
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    })

    # Characters illegal in a Python identifier / in a path segment on Windows
    _ILLEGAL_PY_CHARS = re.compile(r"[^0-9A-Za-z_]")
    _ILLEGAL_FILE_CHARS = re.compile(r'[<>:"/\\|?*.\x00-\x1f]')

    def __init__(self) -> None:
        self._used: set[str] = set(self._RESERVED_PY_NAMES)

    def valid_name(self, possible_name) -> str:
        """Return a unique name that is both a valid Python identifier and a
        filesystem-safe file/folder name, based on ``possible_name``.

        Applies the filesystem sanitisation followed by the Python identifier
        sanitisation, so any character illegal in either is replaced with
        ``_`` and leading underscores are stripped. Raises ``ValueError`` when
        no valid name can be formed (empty result, a leading digit, or a
        Windows reserved device name). The chosen name is registered so it is
        not handed out again.
        """
        return self._nonduplicated(
            self._valid_py_object_name(
                self._valid_explorer_name(possible_name)
            )
        )

    def valid_py_object_name(self, possible_name: str) -> str:
        """Return a unique, valid Python identifier based on ``possible_name``.

        Only characters that are illegal in an identifier are replaced with
        ``_``; the rest of the name is preserved. Leading underscores are
        stripped so the result never starts with ``_``. Raises ``ValueError``
        when no valid name can be formed (empty result, or a leading digit).
        The chosen name is registered so it is not handed out again.
        """
        return self._nonduplicated(
            self._valid_py_object_name(possible_name)
        )

    def _valid_py_object_name(self, possible_name: str) -> str:
        name = self._ILLEGAL_PY_CHARS.sub("_", possible_name).lstrip("_")

        if not name or name[0].isdigit():
            raise ValueError(f"Cannot derive a valid Python name from {possible_name!r}")

        return name

    def valid_explorer_name(self, possible_name: str) -> str:
        """Return a unique, filesystem-safe file/folder name from ``possible_name``.

        Only characters that are illegal in a path segment are replaced with
        ``_``; the rest of the name is preserved. Leading underscores are
        stripped so the result never starts with ``_``. Raises ``ValueError``
        when no valid name can be formed (empty result, or a Windows reserved
        device name). The chosen name is registered so it is not handed out
        again.
        """
        return self._nonduplicated(
            self._valid_explorer_name(possible_name)
        )

    def _valid_explorer_name(self, possible_name: str) -> str:
        name = self._ILLEGAL_FILE_CHARS.sub("_", possible_name).lstrip("_")

        if not name or name.upper() in self._RESERVED_FILE_NAMES:
            raise ValueError(f"Cannot derive a valid file/folder name from {possible_name!r}")

        return name

    def _nonduplicated(self, possible_name: str) -> str:
        """Return ``possible_name`` (or a numbered variant) not already used,
        then register the chosen name."""
        name = possible_name
        suffix = 0
        while name in self._used:
            suffix += 1
            name = f"{possible_name}_{suffix}"

        self._used.add(name)
        return name
