from typing import Literal, TypeAlias, Union

from .utils import flatten_literal_args

SqlServerODBC: TypeAlias = Literal[
    "ODBC Driver 17 for SQL Server",
    "ODBC Driver 11 for SQL Server",
    "SQL Server",
]

SqlServerNative: TypeAlias = Literal[
    "SQL Server Native Client 11.0",
    "SQL Server Native Client 10.0",
]

SqlServerDrivers: TypeAlias = Union[SqlServerODBC, SqlServerNative]

ProvenDrivers: TypeAlias = SqlServerDrivers # Union[SqlServerDrivers]

AllDrivers: TypeAlias = Union[ProvenDrivers, str]

def is_proven_driver(driver: AllDrivers):
    return driver in flatten_literal_args(ProvenDrivers)

