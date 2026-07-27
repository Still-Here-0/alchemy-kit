from dataclasses import dataclass, fields
from typing import Any, Optional

from ...types.model_metadata import ForeignKeyMeta


@dataclass
class ColumnMetadata:
    identity: bool                     = False
    computed: bool                     = False
    primary_key: bool                  = False
    has_default: bool                  = False
    default: str | None                = None
    scale: int | None                  = None
    precision: int | None              = None
    collation: str | None              = None
    original_type: str | None          = None
    foreign_key: ForeignKeyMeta | None = None
    check_constraints: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if value != f.default:
                result[f.name] = value
        return result

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> "ColumnMetadata":
        if not data:
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def __bool__(self) -> bool:
        return bool(self.to_dict())
