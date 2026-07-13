from pandera.pandas import Field
from pandera.typing import Series

from ..base_model import BaseModel

__all__ = [
    "ListSchemas",
    "ListObjects",
    "ListColumns",
    "ListUniqueClusters",
    "ListForeignKeys",
    "ListCheckConstraints",
]


class ListSchemas(BaseModel):
    """Schema for the schema-listing frame (one row per user schema)."""

    name: Series[str] = Field(nullable=False)


class ListObjects(BaseModel):
    """Schema for the object-listing frame (one row per table/view)."""

    object_name: Series[str] = Field(nullable=False)
    object_type: Series[str] = Field(nullable=False)
    object_description: Series[str] = Field(nullable=True)


class ListColumns(BaseModel):
    """Schema for the column-listing frame (one row per table/view column)."""

    column_name: Series[str] = Field(nullable=False)
    sql_type: Series[str] = Field(nullable=False)
    is_nullable: Series[bool] = Field(nullable=False)
    is_identity: Series[bool] = Field(nullable=False)
    is_computed: Series[bool] = Field(nullable=False)
    max_length: Series[int] = Field(nullable=False)
    precision: Series[int] = Field(nullable=False)
    scale: Series[int] = Field(nullable=False)
    collation_name: Series[str] = Field(nullable=True)
    has_default: Series[bool] = Field(nullable=False)
    default_value: Series[str] = Field(nullable=True)
    is_unique: Series[bool] = Field(nullable=False)
    is_primary_key: Series[bool] = Field(nullable=False)
    is_foreign_key: Series[bool] = Field(nullable=False)
    fk_ref_schema: Series[str] = Field(nullable=True)
    fk_ref_table: Series[str] = Field(nullable=True)
    fk_ref_column: Series[str] = Field(nullable=True)
    description: Series[str] = Field(nullable=True)


class ListUniqueClusters(BaseModel):
    """Schema for the unique-cluster frame.

    One row per uniqueness rule that is not a single-column plain unique
    (those fold into ``ListColumns.is_unique``): multi-column PKs, unique
    constraints, unique indexes, and filtered unique indexes of any width.
    ``filter_definition`` holds the WHERE clause of filtered/partial indexes
    and is null for unconditional rules.
    """

    key_name: Series[str] = Field(nullable=False)
    is_primary_key: Series[bool] = Field(nullable=False)
    is_unique_constraint: Series[bool] = Field(nullable=False)
    is_unique: Series[bool] = Field(nullable=False)
    index_type: Series[str] = Field(nullable=False)
    column_count: Series[int] = Field(nullable=False)
    columns: Series[str] = Field(nullable=False)
    filter_definition: Series[str] = Field(nullable=True)


class ListForeignKeys(BaseModel):
    """Schema for the foreign-key frame (one row per FK constraint).

    ``columns`` and ``ref_columns`` are comma-separated, key-ordinal ordered
    and parallel: the i-th local column references the i-th referenced column.
    """

    fk_name: Series[str] = Field(nullable=False)
    ref_schema: Series[str] = Field(nullable=False)
    ref_table: Series[str] = Field(nullable=False)
    columns: Series[str] = Field(nullable=False)
    ref_columns: Series[str] = Field(nullable=False)
    on_delete: Series[str] = Field(nullable=False)
    on_update: Series[str] = Field(nullable=False)


class ListCheckConstraints(BaseModel):
    """Schema for the check-constraint frame (one row per CHECK).

    ``column_name`` is the column the check is attributed to for
    single-column checks, and null for table-level checks.
    """

    check_name: Series[str] = Field(nullable=False)
    definition: Series[str] = Field(nullable=False)
    column_name: Series[str] = Field(nullable=True)
