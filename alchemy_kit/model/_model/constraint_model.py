class ForeignKeyConstraintModel:
    """A table-level foreign key, which may span multiple columns.

    ``columns`` and ``ref_columns`` are parallel, ordered lists: the i-th local
    column references the i-th referenced column. ``on_delete``/``on_update``
    hold the referential actions as reported by the source dialect (e.g.
    ``NO_ACTION``, ``CASCADE``, ``SET_NULL``, ``SET_DEFAULT`` on SQL Server).
    """

    def __init__(
        self,
        name: str,
        columns: list[str],
        ref_schema: str,
        ref_table: str,
        ref_columns: list[str],
        on_delete: str,
        on_update: str,
    ) -> None:
        self.name = name
        self.columns = columns
        self.ref_schema = ref_schema
        self.ref_table = ref_table
        self.ref_columns = ref_columns
        self.on_delete = on_delete
        self.on_update = on_update


class FilteredUniqueIndexModel:
    """A unique index restricted by a WHERE clause (partial/filtered index).

    Uniqueness only holds among rows matching ``definition``, so it must not be
    folded into an unconditional unique constraint.
    """

    def __init__(self, name: str, columns: list[str], definition: str) -> None:
        self.name = name
        self.columns = columns
        self.definition = definition


class CheckConstraintModel:
    """A CHECK constraint on a table/view.

    ``column`` is the column the check is attached to for column-level checks,
    and ``None`` for table-level checks.
    """

    def __init__(self, name: str, definition: str, column: str | None) -> None:
        self.name = name
        self.definition = definition
        self.column = column
