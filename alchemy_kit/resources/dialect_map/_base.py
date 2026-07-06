from abc import ABC, abstractmethod
from typing import ClassVar, Protocol, runtime_checkable

from ...types.dialect_types import DialectTypes


@runtime_checkable
class ColumnLike(Protocol):
    """Structural description of what a renderer needs from a column.

    ``ColumnModel`` satisfies this without ``resources`` importing from
    ``model``, keeping the dependency direction one-way (model -> resources).
    """

    type: str
    max_length: int | None
    precision: int | None
    scale: int | None


class DialectMap[_TypeParameters: str](ABC):
    """Base class for per-dialect SQL <-> Python type resources.

    Generic over ``_TypeParameters``: the ``Literal`` of valid SQL type names
    for the dialect (e.g. ``MssqlTypeParameters``). This carries the type-name
    set at the *type level*, so callers holding a concrete map (or a model that
    exposes one) get dialect-specific autocomplete on APIs typed against
    ``_TypeParameters``.

    Concrete dialects also narrow ``py_types`` to ``dict[SqlType, str]`` so a
    typo'd key is flagged statically; a runtime guard enforces completeness.
    ``dialect_paramaters`` is the runtime companion of ``_TypeParameters`` —
    the same names as a ``frozenset`` for membership checks.
    """
    dialect: ClassVar[DialectTypes]
    dialect_paramaters: ClassVar[frozenset[str]]
    py_types: ClassVar[dict[str, str]]

    @classmethod
    def get_py_type(cls, sql_type: str) -> str:
        """Map a raw SQL type name to the Python type name for the model."""
        try:
            return cls.py_types[sql_type.lower()]
        except KeyError:
            raise ValueError(
                f"{cls.__name__}: no Python mapping for SQL type {sql_type!r}"
            ) from None

    @classmethod
    @abstractmethod
    def render_type(cls, column: ColumnLike) -> str:
        """Render the fully-parameterised SQL type, e.g. ``nvarchar(200)``."""
        raise NotImplementedError("Method called from a abstract class")

    @classmethod
    def str_length(cls, column: ColumnLike) -> int | None:
        """Maximum length (in characters) for a bounded string column.

        Returns ``None`` when the column is not a length-bounded string type
        (e.g. numeric types, or unbounded strings such as ``varchar(max)``).
        """
        raise NotImplementedError("Method called from a abstract class")

