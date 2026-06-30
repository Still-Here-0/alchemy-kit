from typing import NamedTuple, TypeAlias, TYPE_CHECKING

import sqlalchemy

if TYPE_CHECKING:
    from ..connect._info import ConnectionInfo
    from ..connect._engine_handler import EngineHandler

class EngineInfo(NamedTuple):
    engine: sqlalchemy.Engine
    con_info: "ConnectionInfo"
    handlers: list["EngineHandler"]

EnginePool: TypeAlias = dict[str, EngineInfo]
