from abc import ABC, abstractmethod
from typing import ClassVar, Protocol, runtime_checkable


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


class DialectParameterMap(ABC):
    """Base class for per-dialect SQL <-> Python type resources.

    Concrete dialects define their own ``SqlType`` ``Literal`` (the exhaustive
    set of type names) and narrow ``py_types`` to ``dict[SqlType, str]`` so a
    typo'd key is flagged statically; a runtime guard enforces completeness.
    """

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
        ...
