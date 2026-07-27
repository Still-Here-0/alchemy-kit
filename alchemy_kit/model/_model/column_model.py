class ForeignKeyModel:

    def __init__(self, schema: str, table: str, column: str) -> None:
        self.schema = schema
        self.table = table
        self.column = column

class ColumnModel:

    def __init__(
        self,
        name: str,
        column_type: str,
        is_nullable: bool,
        is_identity: bool,
        is_computed: bool,
        max_length: int | None,
        precision: int | None,
        scale: int | None,
        collation_name: str | None,
        has_default: bool,
        default: str | None,
        is_unique: bool,
        is_primary_key: bool,
        is_foreign_key: bool,
        description: str | None,
        fk_ref: ForeignKeyModel | None,
    ) -> None:
        self.name = name
        self.type = column_type
        self.is_nullable = is_nullable
        self.is_identity = is_identity
        self.is_computed = is_computed
        self.max_length = max_length
        self.precision = precision
        self.scale = scale
        self.collation_name = collation_name
        self.has_default = has_default
        self.default = default
        self.is_unique = is_unique
        self.is_primary_key = is_primary_key
        self.is_foreign_key = is_foreign_key
        self.description = description
        self.fk_ref = fk_ref

    @property
    def is_optional(self) -> bool:
        """Whether the column may be omitted from a validated DataFrame because
        the database supplies it: defaulted, computed or identity columns."""
        return self.has_default or self.is_computed or self.is_identity

