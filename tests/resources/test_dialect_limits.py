import pytest

from alchemy_kit.resources.dialect_map import get_map
from alchemy_kit.types.dialect_types import DialectTypes
from alchemy_kit.types.statement_limits import StatementLimits


@pytest.mark.parametrize("dialect", list(DialectTypes))
def test_every_dialect_declares_usable_statement_limits(dialect: DialectTypes):
    limits = get_map(dialect).limits

    assert isinstance(limits, StatementLimits)
    assert 0 < limits.param_budget <= limits.max_params


@pytest.mark.parametrize(
    "dialect",
    [dialect for dialect in DialectTypes if dialect is not DialectTypes.MSSQL],
)
def test_only_mssql_caps_values_rows_independently_of_parameters(dialect: DialectTypes):
    assert get_map(dialect).limits.max_values_rows is None
