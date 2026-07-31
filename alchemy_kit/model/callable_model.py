from typing import TYPE_CHECKING, Any

from ..types.model_metadata import CallMetaData, CallParameter

if TYPE_CHECKING:
    from ..connect._engine_handler import EngineHandler
    from .units._call_unit import CallableUnit

__all__ = ["CallableModel", "CallMetaData", "CallParameter"]


class CallableModel:
    """Base of a generated model for a callable database object (a stored
    procedure), mirroring :class:`BaseModel` and reached as a unit through
    :meth:`EngineHandler.get_unit`."""

    @classmethod
    def _get_unit(cls, handler: "EngineHandler[Any]") -> "CallableUnit":
        """Return a :class:`CallableUnit` for this procedure bound to
        ``handler``'s connection; called by :meth:`EngineHandler.get_unit`."""
        from .units._call_unit import CallableUnit

        return CallableUnit(cls, handler)

    class Config:
        """Identifying settings for the callable."""

        metadata: CallMetaData
