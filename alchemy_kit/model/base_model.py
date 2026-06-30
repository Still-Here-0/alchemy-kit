
from pandera.pandas import DataFrameModel
from pandera.api.base.model import MetaModel
from pandera.typing import DataFrame
from typing import Self, TypedDict, cast
import copy
import pandas as pd

from ..types.errors._model_validation_error import ModelValidationError


class _MetaData(TypedDict):
    schema_name: str
    obj_name: str
    obj_type: str
    reference_name: str
    description: str

class _BaseModelMeta(MetaModel):
    def __init__(self, name, bases, namespace) -> None:
        super().__init__(name, bases, namespace)

class BaseModel(DataFrameModel, metaclass=_BaseModelMeta):

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
    ) -> DataFrame[Self]:
        try:
            check_obj = cls._strip_timezone(check_obj)

            if drop_invalid_rows:
                schema = copy.deepcopy(cls.to_schema())
                schema.drop_invalid_rows = True
                return cast(
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

            return super().validate(
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
    
    @classmethod
    def to_model(cls):
        ...

    class Config(DataFrameModel.Config):
        coerce = True
        strict = False
        drop_invalid_rows: bool = False

        # Changes based on sql object
        unique: list[str] | list[list[str]] | None = None  # pyright: ignore[reportIncompatibleVariableOverride]
        metadata: _MetaData  # pyright: ignore[reportIncompatibleVariableOverride]

