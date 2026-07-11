from abc import ABC, abstractmethod
from typing import Any, ClassVar, NamedTuple, Protocol, runtime_checkable

from ...types.dialect_types import DialectTypes


class ReflectedTypeFacts(NamedTuple):
    """Column type facts extracted from a reflected SQLAlchemy type object,
    normalized to the same conventions the dialect ``.sql`` metadata queries
    use (``max_length == -1`` for unbounded strings, ``0`` when a parameter
    does not apply)."""

    sql_type: str
    max_length: int
    precision: int
    scale: int
    collation: str | None


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
    def reflected_type_facts(cls, sa_type: Any) -> ReflectedTypeFacts:
        """Extract ``(sql_type, max_length, precision, scale, collation)`` from
        a reflected SQLAlchemy type object.

        The type name is the lowercased class name, which for dialect-specific
        reflected types matches the dialect's SQL type name (``NVARCHAR`` ->
        ``nvarchar``). A string type whose ``length`` is ``None`` is unbounded
        and reported as ``-1``; parameters a type does not carry are ``0``.
        Dialects with different conventions override this.
        """
        length = getattr(sa_type, "length", None)
        if hasattr(sa_type, "length") and length is None:
            max_length = -1
        else:
            max_length = length or 0

        return ReflectedTypeFacts(
            sql_type=type(sa_type).__name__.lower(),
            max_length=max_length,
            precision=getattr(sa_type, "precision", None) or 0,
            scale=getattr(sa_type, "scale", None) or 0,
            collation=getattr(sa_type, "collation", None),
        )

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

