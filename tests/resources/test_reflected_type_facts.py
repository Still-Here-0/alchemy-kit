import sqlalchemy
from sqlalchemy.dialects import mssql

from alchemy_kit.resources.dialect_map import DialectMap
from alchemy_kit.resources.dialect_map.mssql import MssqlMap


def test_generic_facts():
    facts = DialectMap.reflected_type_facts(sqlalchemy.INTEGER())
    assert facts == ("integer", 0, 0, 0, None)


def test_generic_string_facts():
    facts = DialectMap.reflected_type_facts(sqlalchemy.VARCHAR(50))
    assert facts.sql_type == "varchar"
    assert facts.max_length == 50

    unbounded = DialectMap.reflected_type_facts(sqlalchemy.VARCHAR())
    assert unbounded.max_length == -1


def test_generic_numeric_facts():
    facts = DialectMap.reflected_type_facts(sqlalchemy.NUMERIC(10, 2))
    assert facts.sql_type == "numeric"
    assert facts.precision == 10
    assert facts.scale == 2


def test_mssql_nchar_reports_bytes():
    facts = MssqlMap.reflected_type_facts(mssql.NVARCHAR(100))
    assert facts.sql_type == "nvarchar"
    assert facts.max_length == 200

    assert MssqlMap.reflected_type_facts(mssql.VARCHAR(100)).max_length == 100
    assert MssqlMap.reflected_type_facts(mssql.NVARCHAR(None)).max_length == -1


def test_mssql_dialect_type_names_map_to_py_types():
    for sa_type in [mssql.NVARCHAR(10), mssql.DATETIME2(), mssql.UNIQUEIDENTIFIER(), mssql.MONEY(), mssql.BIT(), mssql.TINYINT()]:
        facts = MssqlMap.reflected_type_facts(sa_type)
        assert facts.sql_type in MssqlMap.py_types
