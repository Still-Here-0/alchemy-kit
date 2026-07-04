from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from ...resources._dialect_map import get_str_length, get_type
from ...resources._identifiers import Identifiers
from ...types import DialectTypes
from .._model.column_model import ColumnModel
from .._model.object_model import ObjectModel
from ._column_metadata import ColumnMetadata, ForeignKeyMeta


@dataclass(kw_only=True)
class StubFileBuilder:
    template: ClassVar[Path] = Path(__file__).resolve().parent/"py_template_file.txt"
    column_template: ClassVar[str] = "    {column_name}: {column_type} = pa.Field({column_parameters})"
    identifiers: Identifiers = field(default_factory=Identifiers, init=False, repr=False)

