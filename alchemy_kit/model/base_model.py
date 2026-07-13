
import copy
from typing import TYPE_CHECKING, Any, ClassVar, Iterator, NotRequired, Self, TypedDict, cast

import pandas as pd
from pandera.api.base.model import MetaModel
from pandera.pandas import DataFrameModel
from pandera.typing import DataFrame

from ..resources._sql import SQL
from ..resources.dialect_map import DialectMap
from ..types.dialect_types import DialectTypes
from ..types.errors._model_validation_error import ModelValidationError

if TYPE_CHECKING:
    from ..connect._engine_handler import EngineHandler
    from ._builders._column_metadata import ForeignKeyMeta
    from .units._object_unit import ObjectUnit

__all__ = ["MetaData", "BaseModel"]

class MetaData(TypedDict):
    """Identifying metadata for the SQL object a model represents."""

    schema_name: str
    obj_name: str
    obj_type: str
    reference_name: str
    description: str | None
    unparsed_checks: NotRequired[dict[str, str]]
    unparsed_indexes: NotRequired[dict[str, str]]


class _BaseModelMeta(MetaModel):
    def __init__(self, name, bases, namespace) -> None:
        super().__init__(name, bases, namespace)

class BaseModel[_TypeParameters: str](DataFrameModel, metaclass=_BaseModelMeta):
    """Base pandera model that validates a DataFrame against a SQL object's schema."""

    _dialect: ClassVar[DialectTypes]
    _map: ClassVar[type[DialectMap[Any]]]

    @classmethod
    def _strip_timezone(cls, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        schema = cls.to_schema()

        for name, info in schema.columns.items():
            if name not in df.columns:
                continue

            dtype = getattr(info, "dtype", None)
            pd_dtype = getattr(dtype, "type", None) if dtype is not None else None

            if pd_dtype is None or not pd.api.types.is_datetime64_any_dtype(pd_dtype):
                continue

            series = pd.to_datetime(df[name], errors="coerce", utc=True)

            if getattr(series.dt, "tz", None) is not None:
                series = series.dt.tz_convert(None)

            df[name] = series

        return df

    @classmethod
    def validate(  # pyright: ignore[reportIncompatibleMethodOverride]
        cls,
        check_obj: pd.DataFrame,
        head: int | None = None,
        tail: int | None = None,
        sample: int | None = None,
        random_state: int | None = None,
        lazy: bool = False,
        inplace: bool = False,
        drop_invalid_rows: bool = False,
        handler: "EngineHandler | None" = None,
    ) -> DataFrame[Self]:
        """Validate a DataFrame against this model, stripping timezones first.

        When ``handler`` is given, an online tier runs after the offline
        (shape + checks) validation: every foreign-key column recorded in the
        model's metadata is checked for referential integrity against the
        referenced tables, through that connection.
        """
        try:
            check_obj = cls._strip_timezone(check_obj)

            if drop_invalid_rows:
                schema = copy.deepcopy(cls.to_schema())
                schema.drop_invalid_rows = True
                validated = cast(
                    DataFrame[Self],
                    schema.validate(
                        check_obj,
                        head=head,
                        tail=tail,
                        sample=sample,
                        random_state=random_state,
                        lazy=True,
                        inplace=inplace,
                    ),
                )
            else:
                validated = super().validate(
                    check_obj,
                    head=head,
                    tail=tail,
                    sample=sample,
                    random_state=random_state,
                    lazy=lazy,
                    inplace=inplace,
                )
        except Exception as exc:
            raise ModelValidationError(f"[{cls.__name__}] {exc}") from exc

        if handler is not None:
            failures = cls.validate_foreign_keys(validated, handler)
            if failures:
                raise ModelValidationError(
                    f"[{cls.__name__}] foreign key values not found in referenced tables: {failures}"
                )

        return validated

    @classmethod
    def iter_foreign_keys(cls) -> Iterator[tuple[str, "ForeignKeyMeta"]]:
        """Yield ``(column_name, foreign_key)`` for every column whose generated
        metadata records a foreign-key reference. Column names are the SQL
        (alias) names, matching the DataFrame's columns."""
        from ._builders._column_metadata import ColumnMetadata

        for name, column in cls.to_schema().columns.items():
            metadata = ColumnMetadata.from_dict(column.metadata)
            if metadata.foreign_key is not None:
                yield str(name), metadata.foreign_key

    @classmethod
    def validate_foreign_keys(cls, check_obj: pd.DataFrame, handler: "EngineHandler") -> dict[str, set[Any]]:
        """Check that every FK column's values exist in the referenced table.

        Queries each referenced table once (deduplicated ``IN`` list) through
        ``handler`` and returns the missing values per column; an empty dict
        means full referential integrity.
        """
        failures: dict[str, set[Any]] = {}

        for column_name, foreign_key in cls.iter_foreign_keys():
            if column_name not in check_obj.columns:
                continue

            keys = check_obj[column_name].dropna().unique().tolist()
            if not keys:
                continue

            schema_ref = handler.quote_identifier(foreign_key["schema"])
            table_ref = handler.quote_identifier(foreign_key["table"])
            column_ref = handler.quote_identifier(foreign_key["column"])

            sql = SQL(
                raw_query=(
                    f"SELECT DISTINCT {column_ref} FROM {schema_ref}.{table_ref}"
                    f" WHERE {column_ref} IN :fk_keys"
                ),
                query_parameters={"fk_keys": keys},
            )
            _, existing = handler.run_sql(sql)

            missing = set(keys) - set(existing.iloc[:, 0]) if not existing.empty else set(keys)
            if missing:
                failures[column_name] = missing

        return failures
    
    @classmethod
    def get_unit(cls) -> "ObjectUnit[_TypeParameters]":
        """Return an :class:`ObjectUnit` for this model, dialect-typed so column
        access and ``cast`` autocomplete the model's own SQL type names."""
        from .units._object_unit import ObjectUnit

        return ObjectUnit(cls)

    class Config(DataFrameModel.Config):
        """Pandera validation settings for the model."""

        coerce = True
        strict = False
        drop_invalid_rows: bool = False

        # Changes based on sql object
        unique: list[str] | list[list[str]] | None = None  # pyright: ignore[reportIncompatibleVariableOverride]
        metadata: MetaData  # pyright: ignore[reportIncompatibleVariableOverride]

