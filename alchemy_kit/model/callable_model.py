from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from ..connect._engine_handler import EngineHandler
    from .units._call_unit import CallableUnit

__all__ = ["CallableModel", "CallMetaData", "CallParameter"]


class CallParameter(TypedDict):
    """One stored-procedure parameter as recorded on a callable model."""

    name: str
    sql_type: str
    is_nullable: bool
    mode: str


class CallMetaData(TypedDict):
    """Identifying metadata for the stored procedure a callable model represents."""

    schema_name: str
    name: str
    reference_name: str
    description: str | None
    parameters: list[CallParameter]


class CallableModel[_TypeParameters: str]:
    """Base of a generated model for a callable database object (a stored
    procedure). Generic over the dialect's SQL type names (``_TypeParameters``),
    mirroring :class:`BaseModel`, and reached as a unit through
    :meth:`EngineHandler.get_unit`."""

    @classmethod
    def _get_unit(cls, handler: "EngineHandler") -> "CallableUnit[_TypeParameters]":
        """Return a :class:`CallableUnit` for this procedure bound to
        ``handler``'s connection; called by :meth:`EngineHandler.get_unit`."""
        from .units._call_unit import CallableUnit

        return CallableUnit(cls, handler)

    class Config:
        """Identifying settings for the callable."""

        metadata: CallMetaData
