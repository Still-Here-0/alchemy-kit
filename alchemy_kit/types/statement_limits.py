from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StatementLimits:
    """How much one prepared statement may carry on a dialect.

    Attributes:
        max_params: The server's documented cap on parameters per statement.
            SQLite's default is 32766 on 3.32 and later (999 before that).
        driver_reserved_params: Slots the driver spends wrapping the statement,
            before any of the caller's own parameters are counted. pyodbc sends
            a parameterised statement as ``sp_executesql @stmt, @params, @p1,
            ...``, so the statement text and the parameter declaration consume
            2 of SQL Server's 2100.
        max_values_rows: Cap on rows in one ``INSERT ... VALUES`` clause, where
            the dialect sets one independently of the parameter count; ``None``
            when only the parameter budget bounds it.
    """

    max_params: int
    driver_reserved_params: int = 0
    max_values_rows: int | None = None

    @property
    def param_budget(self) -> int:
        """Parameters a caller may actually bind in one statement."""
        return self.max_params - self.driver_reserved_params
