from typing import Any

import pandas as pd
from sqlalchemy.sql.expression import Update

from ..model.units import BooleanColumnUnit, ColumnUnit, ObjectUnit
from ..resources._sql import SQL
from ..types.typestate import Set, Unset
from ._base import SqlBuilder
from ._utils import _Assignment

# S -> set_values()
# W -> where()
class UpdateBuilder[S, W](SqlBuilder):
    def __new__(cls, target: ObjectUnit[Any]) -> UpdateBuilder[Unset, Unset]: ...
    def __init__(self, target: ObjectUnit[Any]) -> None: ...
    def _statement(self) -> Update: ...
    def set_values(
        self: UpdateBuilder[Unset, W],
        assignment: _Assignment,
        *assignments: _Assignment,
    ) -> UpdateBuilder[Set, W]: ...
    def where(
        self: UpdateBuilder[S, Unset],
        *conditions: BooleanColumnUnit[Any],
    ) -> UpdateBuilder[S, Set]: ...
    def returning(
        self: UpdateBuilder[S, W],
        *columns: ColumnUnit[Any],
    ) -> UpdateBuilder[S, W]: ...
    def to_sql(self: UpdateBuilder[Set, W], **parameters: Any) -> SQL: ...
    def render(self: UpdateBuilder[Set, W]) -> str: ...
    def run(
        self: UpdateBuilder[Set, W],
        **parameters: Any,
    ) -> tuple[int | None, pd.DataFrame]: ...
