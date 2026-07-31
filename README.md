# alchemy-kit

A typed, reflection-generated, multi-dialect, DataFrame-first SQL toolkit for
Python. It reflects your database into typed models, builds queries through a
fluent, autocomplete-friendly API, and returns pandas DataFrames with pandera
validation — not a classic object-graph ORM.

## What it solves

Writing SQL against a real database in Python usually means one of two painful
extremes: raw strings that no editor understands and that break silently when
the schema changes, or a heavyweight object-graph ORM that hides the SQL and
fights you the moment you need analytics-style queries.

alchemy-kit sits in between:

- **Your schema becomes typed Python.** It reflects your live database and
  generates one model per table/view/procedure, so column names, types and
  nullability are known to your editor and type checker.
- **Queries are built, not concatenated.** A fluent builder produces the SQL;
  invalid column references and cross-connection mistakes are caught before the
  query ever runs.
- **Results are DataFrames.** Every query returns a pandas DataFrame, so it
  drops straight into analysis, ETL and data pipelines.
- **One API, many databases.** The same code targets SQL Server, PostgreSQL,
  MySQL, MariaDB, Oracle and SQLite; dialect differences are handled for you.
- **The library owns transactions.** Commit/rollback boundaries are managed
  internally, including all-or-nothing multi-statement runs.

In practice that means you work with tables and explicit joins that return
DataFrames, rather than lazily-loaded object graphs.

## Supported databases

SQL Server · PostgreSQL · MySQL · MariaDB · Oracle · SQLite

## Installation

```bash
pip install alchemy-kit
```

Database drivers are optional extras — install the one you need, e.g.:

```bash
pip install "alchemy-kit[mssql]"
```

Requires Python 3.12+.

## Quick start

### 1. Generate typed models from your database

`build` reflects the schema and writes a typed model module per object into the
target directory.

```python
from pathlib import Path

import sqlalchemy

from alchemy_kit.connect import ConnectionInfo
from alchemy_kit.model import build

conn = ConnectionInfo(sqlalchemy.make_url("sqlite:///shop.db"))

build(conn, Path("./models"), clear_result_dir=True)
```

For richer connections (auth methods, drivers, TLS) use the `info_builder`
helpers instead of a raw URL, e.g. `info_builder.from_values_mssql(...)`.

### 2. Query with the typed builder

Open a connection, get a typed handle on a table, and build a `SELECT`. Every
query returns a `(row_count, DataFrame)` pair.

```python
import sqlalchemy

from alchemy_kit.connect import ConnectionInfo, EngineManager
from alchemy_kit.builder import SelectBuilder

from models.items_MODULE import items  # generated in step 1

conn = ConnectionInfo(sqlalchemy.make_url("sqlite:///shop.db"))

with EngineManager(None) as manager:
    handler = manager.create_engine(conn)

    # A typed handle on the table, bound to this connection and dialect.
    table = handler.get_unit(items)

    # SELECT name, price FROM items WHERE price > 1 ORDER BY price DESC
    _, df = (
        SelectBuilder(table.name, table.price, from_=table)
          .where(table.price > 1)
          .order_by(table.price.desc())
    ).run()
    print(df)
```

`table.price`, `table.name`, ... are the model's columns, so typos and type
mismatches are flagged by your editor. The builder also covers `join`,
`group_by`, `having`, `distinct`, `limit`/`offset`, `paginate`, aggregates
(`sum`, `avg`, `count`, ...) and window functions (`row_number`, `rank`,
`lag`/`lead`, `over`).

Tell the connection which dialect to expect and its SQL type names ride along
too, so `cast` is checked against that database's own types:

```python
from alchemy_kit.connect import info_builder
from alchemy_kit.dialects import MssqlMap

conn = info_builder.from_env(".env", expect=MssqlMap)  # raises if the URL is not MSSQL

with EngineManager(None) as manager:
    handler = manager.create_handler(conn)      # carries MSSQL's type names
    table = handler.get_unit(items)

    table.price.cast("decimal")                 # checked; "clob" would not compile
```

`alchemy_kit.dialects` holds one map per database — `MssqlMap`,
`PostgresqlMap`, `MysqlMap`, `MariadbMap`, `OracleMap`, `SqliteMap`. Passing
one is optional: leave it out and everything still runs, you just lose the
`cast` checking. The same argument works on `ConnectionInfo`, `from_json` and
`EngineManager.get_handler`.

`from_json` builds one named connection at a time, so a file describing several
databases gives each of them its own map — and only the entry you name is
built:

```python
prod  = info_builder.from_json("connections.json", "prod",  expect=MssqlMap)
cache = info_builder.from_json("connections.json", "cache", expect=SqliteMap)
```

The name may be left out only when the file holds exactly one connection.

### 3. Write data

```python
from alchemy_kit.builder import InsertBuilder, UpdateBuilder, DeleteBuilder

# INSERT a single row — (column, value) pairs, like set_values above
InsertBuilder(table).from_values((table.id_1, 1), (table.name, "bolt"), (table.price, 0.5)).run()

# Bulk INSERT a DataFrame, chunked
InsertBuilder(table).from_dataframe(df).run(chunk_size=1_000)

# UPDATE items SET price = price * 2 WHERE name = 'bolt'
UpdateBuilder(table).set_values((table.price, table.price * 2)).where(table.name == "bolt").run()

# DELETE FROM items WHERE price < 1
DeleteBuilder(table).where(table.price < 1).run()
```

### 4. Call a stored procedure

Generated procedure models run the same way — the arguments are positional.

```python
from models.recount_stock_CALL import recount_stock  # generated in step 1

proc = handler.get_unit(recount_stock)
_, df = proc.run(42, True)
```

### Validate a DataFrame against a model

Generated models are [pandera](https://pandera.readthedocs.io) schemas, so any
DataFrame can be validated against the table's real shape:

```python
items.validate(df)
```

## Documentation

In-depth developer documentation — covering the architecture and each component
in detail — lives under [`docs/`](docs/). It is still a work in progress and
will be filled out soon.

## Project status

alchemy-kit is under active development. See [docs/STATUS.md](docs/STATUS.md)
for exactly which SQL features are implemented, what is planned (e.g.
`MERGE`/`UPSERT`, persistent-object DDL), and open design questions.
