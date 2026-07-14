import pytest
import sqlalchemy
from sqlalchemy.dialects import mssql
from sqlalchemy.dialects.mssql import base as mssql_base
from sqlalchemy.dialects.mysql import base as mysql_base
from sqlalchemy.dialects.oracle import base as oracle_base
from sqlalchemy.dialects.postgresql import base as postgresql_base
from sqlalchemy.dialects.sqlite import base as sqlite_base

from alchemy_kit.resources.dialect_map import DialectMap
from alchemy_kit.resources.dialect_map.mariadb import MariadbMap
from alchemy_kit.resources.dialect_map.mssql import MssqlMap
from alchemy_kit.resources.dialect_map.mysql import MysqlMap
from alchemy_kit.resources.dialect_map.oracle import OracleMap
from alchemy_kit.resources.dialect_map.postgresql import PostgresqlMap
from alchemy_kit.resources.dialect_map.sqlite import SqliteMap


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


def test_mssql_generic_reflected_classes_resolve_to_dialect_names():
    facts = MssqlMap.reflected_type_facts(sqlalchemy.INTEGER())
    assert facts.sql_type == "int"
    assert MssqlMap.get_py_type(facts.sql_type) == "int"

    assert MssqlMap.reflected_type_facts(sqlalchemy.DOUBLE_PRECISION()).sql_type == "float"


_ISCHEMA_CASES = [
    (MssqlMap, mssql_base.MSDialect),
    (MysqlMap, mysql_base.MySQLDialect),
    (MariadbMap, mysql_base.MySQLDialect),
    (PostgresqlMap, postgresql_base.PGDialect),
    (OracleMap, oracle_base.OracleDialect),
    (SqliteMap, sqlite_base.SQLiteDialect),
]

@pytest.mark.parametrize("dialect_map, sa_dialect", _ISCHEMA_CASES, ids=[case[0].__name__ for case in _ISCHEMA_CASES])
def test_every_supported_ischema_type_resolves(dialect_map: type[DialectMap], sa_dialect):
    for name, type_class in sa_dialect.ischema_names.items():
        if name.lower() not in dialect_map.py_types:
            continue

        facts = dialect_map.reflected_type_facts(type_class())
        assert facts.sql_type in dialect_map.py_types, (
            f"{dialect_map.__name__}: ischema type {name!r} reflects as "
            f"{facts.sql_type!r}, which has no py_types mapping"
        )
