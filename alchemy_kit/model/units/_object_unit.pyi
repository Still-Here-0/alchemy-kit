from sqlalchemy.sql.expression import FromClause

from ...connect._engine_handler import EngineHandler
from ..base_model import BaseModel, MetaData

class ObjectUnit[_TypeParameters: str]:
    _base: type[BaseModel]
    _handler: EngineHandler[_TypeParameters]
    _selectable: FromClause

    def __init__(
        self,
        base: type[BaseModel],
        handler: EngineHandler[_TypeParameters],
        selectable: FromClause | None = ...,
    ) -> None: ...
    def set_alias(self, alias: str) -> ObjectUnit[_TypeParameters]: ...
    def get_metadata(self) -> MetaData: ...
