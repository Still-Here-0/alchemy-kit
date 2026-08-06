from dataclasses import dataclass
from typing import Literal

type ReturningStatement = Literal["INSERT", "UPDATE", "DELETE"]


@dataclass(frozen=True, slots=True)
class ReturningSupport:
    """Which statements a dialect can hand the affected rows back from,
    rendered as ``RETURNING`` or as MSSQL's ``OUTPUT``.

    A dialect whose driver returns the values through OUT bind variables rather
    than a fetchable result (Oracle) counts as no support here.
    """

    insert: bool = False
    update: bool = False
    delete: bool = False

    def allows(self, statement: ReturningStatement) -> bool:
        """Whether the dialect returns rows from ``statement``."""
        return {
            "INSERT": self.insert,
            "UPDATE": self.update,
            "DELETE": self.delete,
        }[statement]
