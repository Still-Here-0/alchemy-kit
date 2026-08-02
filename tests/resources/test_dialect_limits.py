from typing import Any
import pytest

from alchemy_kit.resources.dialect_map import DIALECT_MAPS, DialectMap, MssqlMap
from alchemy_kit.types.statement_limits import StatementLimits


@pytest.mark.parametrize("dialect", list(DIALECT_MAPS))
def test_every_dialect_declares_usable_statement_limits(dialect: type[DialectMap[Any]]):
    limits = dialect.limits

    assert isinstance(limits, StatementLimits)
    assert 0 < limits.param_budget <= limits.max_params


@pytest.mark.parametrize(
    "dialect",
    [dialect for dialect in DIALECT_MAPS if dialect is not MssqlMap],
)
def test_only_mssql_caps_values_rows_independently_of_parameters(dialect: type[DialectMap[Any]]):
    assert dialect.limits.max_values_rows is None
