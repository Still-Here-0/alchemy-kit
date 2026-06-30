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

    def render_sql_type(self) -> str: # TODO: This only works with SQL Server
        t = self.type.lower()

        # String / binary types with a length component.
        length_types_char  = {"char", "varchar"}       # 1 byte/char
        length_types_nchar = {"nchar", "nvarchar"}     # 2 bytes/char (Unicode)
        length_types_bin   = {"binary", "varbinary"}
        if t in length_types_char or t in length_types_nchar or t in length_types_bin:
            if self.max_length is None or self.max_length == -1:
                return f"{t}(max)"
            # SQL Server reports max_length in bytes; nchar/nvarchar use 2 bytes/char.
            if t in length_types_nchar:
                return f"{t}({self.max_length // 2})"
            return f"{t}({self.max_length})"

        # Exact numerics with precision/scale.
        if t in {"decimal", "numeric"}:
            if self.precision is None:
                return t
            if self.scale is None or self.scale == 0:
                return f"{t}({self.precision})"
            return f"{t}({self.precision}, {self.scale})"

        # Approximate numeric — float(n) uses precision (mantissa bits).
        if t == "float":
            if self.precision is not None and self.precision > 0:
                return f"float({self.precision})"
            return "float"

        # Datetime types that accept a fractional-seconds precision (0..7).
        # SQL Server reports it on the `scale` column.
        if t in {"time", "datetime2", "datetimeoffset"}:
            if self.scale is not None:
                return f"{t}({self.scale})"
            return t

        # Everything else: int, bigint, smallint, tinyint, bit, money,
        # smallmoney, real, date, datetime, smalldatetime, uniqueidentifier,
        # text, ntext, xml, image, timestamp, rowversion, sql_variant, ...
        return t
