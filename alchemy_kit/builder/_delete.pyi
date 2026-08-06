from typing import Any

from sqlalchemy.sql.expression import Delete

from ..model.units import BooleanColumnUnit, ColumnUnit, ObjectUnit
from ..types.typestate import Set, Unset
from ._base import SqlBuilder

# W -> where()
class DeleteBuilder[W](SqlBuilder):
    def __new__(cls, target: ObjectUnit[Any]) -> DeleteBuilder[Unset]: ...
    def __init__(self, target: ObjectUnit[Any]) -> None: ...
    def _statement(self) -> Delete: ...
    def where(
        self: DeleteBuilder[Unset],
        *conditions: BooleanColumnUnit[Any],
    ) -> DeleteBuilder[Set]: ...
    def returning(self, *columns: ColumnUnit[Any]) -> DeleteBuilder[W]: ...
