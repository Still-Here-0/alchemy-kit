from typing import Any

from sqlalchemy.sql.expression import Select

from ..model.units import (
    BooleanColumnUnit,
    ColumnUnit,
    ObjectUnit,
    OrderingColumnUnit,
)
from ..types.sql_types import SqlJoinTypes
from ..types.typestate import Set, Unset
from ._base import SqlBuilder

# W -> where()
# G -> group_by()
# D -> distinct()
# L -> limit()
# O -> offset()
class SelectBuilder[W, G, D, L, O](SqlBuilder):
    def __new__(
        cls,
        *columns: ColumnUnit[Any] | ObjectUnit[Any],
        from_: ObjectUnit[Any],
    ) -> SelectBuilder[Unset, Unset, Unset, Unset, Unset]: ...
    def __init__(
        self,
        *columns: ColumnUnit[Any] | ObjectUnit[Any],
        from_: ObjectUnit[Any],
    ) -> None: ...
    def _statement(self) -> Select[Any]: ...
    def as_scalar(self) -> ColumnUnit[Any]: ...
    def as_object(self, name: str) -> ObjectUnit[Any]: ...
    def where(
        self: SelectBuilder[Unset, G, D, L, O],
        *conditions: BooleanColumnUnit[Any],
    ) -> SelectBuilder[Set, G, D, L, O]: ...
    def join(
        self,
        how: SqlJoinTypes,
        other: ObjectUnit[Any],
        on: BooleanColumnUnit[Any] | None = ...,
    ) -> SelectBuilder[W, G, D, L, O]: ...
    def group_by(
        self: SelectBuilder[W, Unset, D, L, O],
        *columns: ColumnUnit[Any],
    ) -> SelectBuilder[W, Set, D, L, O]: ...
    def having(
        self,
        *conditions: BooleanColumnUnit[Any],
    ) -> SelectBuilder[W, G, D, L, O]: ...
    def order_by(
        self,
        *columns: ColumnUnit[Any] | OrderingColumnUnit[Any],
    ) -> SelectBuilder[W, G, D, L, O]: ...
    def distinct(
        self: SelectBuilder[W, G, Unset, L, O],
    ) -> SelectBuilder[W, G, Set, L, O]: ...
    def limit(
        self: SelectBuilder[W, G, D, Unset, O],
        count: int,
    ) -> SelectBuilder[W, G, D, Set, O]: ...
    def offset(
        self: SelectBuilder[W, G, D, L, Unset],
        count: int,
    ) -> SelectBuilder[W, G, D, L, Set]: ...
    def paginate(
        self: SelectBuilder[W, G, D, Unset, Unset],
        page: int,
        size: int,
    ) -> SelectBuilder[W, G, D, Set, Set]: ...
