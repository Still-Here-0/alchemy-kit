from typing import NotRequired, TypedDict

from ._sql_utilities import ParameterMode


class ForeignKeyMeta(TypedDict):
    schema: str
    table: str
    column: str


class MetaData(TypedDict):
    """Identifying metadata for the SQL object a model represents.

    ``db_name`` is ``None`` when the connection URL the model was built from
    names no database (a DSN, or an in-memory SQLite).
    """

    db_name: str | None
    schema_name: str
    obj_name: str
    obj_type: str
    reference_name: str
    description: str | None
    unparsed_checks: NotRequired[dict[str, str]]
    unparsed_indexes: NotRequired[dict[str, str]]


class CallParameter(TypedDict):
    """One stored-procedure parameter as recorded on a callable model."""

    name: str
    sql_type: str
    is_nullable: bool
    mode: ParameterMode


class CallMetaData(TypedDict):
    """Identifying metadata for the stored procedure a callable model represents.

    ``db_name`` is ``None`` when the connection URL the model was built from
    names no database (a DSN, or an in-memory SQLite).
    """

    db_name: str | None
    schema_name: str
    name: str
    reference_name: str
    description: str | None
    parameters: list[CallParameter]
