from ..dialect_types import DialectTypesInput


class StatementLimitError(ValueError):
    """Raised when a statement binds more parameters than the dialect accepts.

    Subclasses ``ValueError`` so callers catching that keep working; ``remedy``
    is supplied by the raiser, which knows whether the fix is to bind fewer
    values or to target fewer columns.
    """

    def __init__(self, dialect: DialectTypesInput, needed: int, budget: int, remedy: str) -> None:
        self.dialect = dialect
        self.needed = needed
        self.budget = budget

        super().__init__(
            f"statement binds {needed} parameters but {dialect} accepts "
            f"{budget} per statement; {remedy}"
        )
