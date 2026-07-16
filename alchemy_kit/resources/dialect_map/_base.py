from abc import ABC, abstractmethod
from typing import Any, Callable, ClassVar, NamedTuple, Protocol, runtime_checkable

import sqlalchemy as sa

from ...types.dialect_types import DialectTypes
from ...types.py_type_parameters import PyTypeParameters

type SaTypeFactory = Callable[[], sa.types.TypeEngine[Any]]


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
    py_types: ClassVar[dict[str, PyTypeParameters]]
    sa_types: ClassVar[dict[str, SaTypeFactory]]
    _reflected_synonyms: ClassVar[dict[str, str]] = {}

    _quote_open: ClassVar[str] = '"'
    _quote_close: ClassVar[str] = '"'

    max_insert_rows: ClassVar[int | None] = None
    max_statement_params: ClassVar[int | None] = None

    @classmethod
    def quote_identifier(cls, name: str) -> str:
        """Quote a schema/table/column name with the dialect's delimiters,
        escaping embedded closing delimiters by doubling them."""
        escaped = name.replace(cls._quote_close, cls._quote_close * 2)
        return f"{cls._quote_open}{escaped}{cls._quote_close}"

    @classmethod
    def render_reference(cls, schema_name: str, object_name: str) -> str:
        """Render the fully-qualified, dialect-quoted object reference,
        e.g. ``[dbo].[orders]`` or ``"public"."orders"``."""
        return f"{cls.quote_identifier(schema_name)}.{cls.quote_identifier(object_name)}"

    @classmethod
    def get_py_type(cls, sql_type: str) -> PyTypeParameters:
        """Map a raw SQL type name to the Python type name for the model."""
        try:
            return cls.py_types[sql_type.lower()]
        except KeyError:
            raise ValueError(
                f"{cls.__name__}: no Python mapping for SQL type {sql_type!r}"
            ) from None

    @classmethod
    def get_sa_type(
        cls,
        sql_type: str | None,
        precision: int | None = None,
        scale: int | None = None,
    ) -> sa.types.TypeEngine[Any]:
        """Map a raw SQL type name to a SQLAlchemy type instance for Core
        compilation, parameterised with ``precision``/``scale`` for numerics.

        ``None`` (a column with no recorded type) compiles as ``NullType``,
        which is valid anywhere a concrete type is not required (it cannot be
        ``CAST`` to). Types the dialect map deliberately assigns ``NullType``
        (e.g. spatial types SQLAlchemy has no class for) behave the same way.
        """
        if sql_type is None:
            return sa.types.NullType()

        try:
            sa_type = cls.sa_types[sql_type.lower()]()
        except KeyError:
            raise ValueError(
                f"{cls.__name__}: no SQLAlchemy mapping for SQL type {sql_type!r}"
            ) from None

        if isinstance(sa_type, sa.Numeric):
            if precision:
                sa_type.precision = precision
            if scale:
                sa_type.scale = scale

        return sa_type

    @classmethod
    def reflected_type_facts(cls, sa_type: Any) -> ReflectedTypeFacts:
        """Extract ``(sql_type, max_length, precision, scale, collation)`` from
        a reflected SQLAlchemy type object.

        The type name is the lowercased class name, which for dialect-specific
        reflected types matches the dialect's SQL type name (``NVARCHAR`` ->
        ``nvarchar``). Dialects sometimes reflect a SQL type as a class whose
        name differs from the type's own name (MSSQL ``int`` ->
        ``sqltypes.INTEGER``); ``_reflected_synonyms`` maps those class names
        back to the dialect's canonical type name. A string type whose
        ``length`` is ``None`` is unbounded and reported as ``-1``; parameters
        a type does not carry are ``0``. Dialects with different conventions
        override this.
        """
        length = getattr(sa_type, "length", None)
        if hasattr(sa_type, "length") and length is None:
            max_length = -1
        else:
            max_length = length or 0

        sql_type = type(sa_type).__name__.lower()
        return ReflectedTypeFacts(
            sql_type=cls._reflected_synonyms.get(sql_type, sql_type),
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

