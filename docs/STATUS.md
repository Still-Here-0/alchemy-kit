# Project Status

What alchemy-kit implements today and what remains. Checked items are done;
unchecked items are planned.

Last updated: 2026-08-05

The user drives DQL, DML and DDL through builders. The library owns TCL
internally (it manages transaction boundaries). DCL will not be implemented.

## Generated Models — Reflection to Python Classes

`build` mirrors a live database into a package of Python classes: one module per
object, holding a pandera `BaseModel` subclass with the object's columns and
constraints, plus a `.pyi` beside it that types the columns and the unit they
resolve to. Everything downstream — units, builders, dialect rendering — reads
what this step recorded.

- [x] Reflect the database into an object graph (parse_db, MetadataExtractor)
  - [x] Read the schemas, tables, views and procedures
  - [x] Read each column's type, nullability, length, precision, scale,
        collation, default, identity and computed flags
  - [x] Read the primary keys, unique constraints and foreign keys
  - [x] Read the check constraints and the filtered unique indexes
  - [x] Read each procedure parameter's name, type, nullability and mode
  - [x] Read the object and column descriptions
  - [x] Narrow the reflected set with SchemaConfig include / exclude rules
  - [x] Fall back to a dialect `.sql` query where reflection falls short
    - Only MSSQL has fallbacks today, for unique and check constraints
  - [ ] Read the procedures the INFORMATION_SCHEMA route misses
    - SQLite and Oracle return none: SQLite has no stored procedures, but Oracle
      keeps its own in its data dictionary
- [x] Generate the model modules (PyFileBuilder, CallablePyFileBuilder)
  - [x] Render one class per table, view and procedure
  - [x] Map every SQL type to its Python type through the dialect map
  - [x] Rename identifiers that are not valid Python names, keeping the SQL name
        in `alias`
  - [x] Translate the parseable column checks into pandera field arguments
  - [x] Translate the column-to-column checks and the filtered unique indexes
        into `@pa.dataframe_check` methods
  - [x] Keep the checks that would not parse verbatim in the metadata
  - [x] Record the column facts the builders later need
    - Identity, computed, primary key, default, precision, scale, collation,
      original type and the foreign key reference
  - [ ] Report what was generated
    - The logger is threaded through `build` and `build_model`, but their log
      calls are still `# TODO` comments
- [x] Generate the stub files (StubFileBuilder, CallableStubFileBuilder)
  - [x] Type the model columns and the object unit's columns
  - [x] Type a procedure's `run` / `to_sql` / `render` from its parameters
- [x] Lay the package out on disk
  - [x] One directory per schema, its `__init__.py` re-exporting each object
  - [x] Group the tables, views and procedures into subfolders on request
- [ ] Draw the reflected schema as an SVG (build_svg)
  - Stubbed today: `build_svg` loops the schemas and does nothing

## Expressions — Column and Object Units

- [x] Object units (ObjectUnit)
  - [x] Resolve a model's field names to their SQL columns
  - [x] Alias an object and carry the alias into every column reference
  - [x] Expose the table metadata recorded on the model
- [x] Value expressions (ColumnUnit)
  - [x] Cast to a SQL type of the connection's dialect
  - [x] Implement the arithmetic and comparison operators
  - [x] Implement the aggregates (SUM / AVG / MIN / MAX / COUNT)
  - [x] Implement COALESCE and NULLIF
  - [x] Implement ABS and ROUND
  - [x] Implement the string functions (LOWER / UPPER / TRIM / LENGTH /
        concatenation)
  - [ ] Implement the substring functions (SUBSTRING / REPLACE / LTRIM / RTRIM)
  - [ ] Implement the date parts and date arithmetic (EXTRACT, date add / diff)
    - The most dialect-divergent area; each spells these differently
  - [x] Apply an arbitrary SQL function by name
    - The escape hatch for anything without a dedicated method
    - [x] Place arguments before the expression, not only after it
      - This expression leads the arguments unless the string `"SELF"` marks
        its place among them, which is what the calls taking it later need —
        `apply("power", 2, "SELF")`,
        `apply("dateadd", OperandUnit.raw("day"), 7, "SELF")`,
        `apply("concat_ws", "-", "SELF")`
- [x] Predicates (BooleanColumnUnit)
  - [x] Combine conditions with AND / OR / NOT
  - [x] Implement IS NULL and IS NOT NULL
  - [x] Implement the null-safe comparisons (IS DISTINCT FROM)
  - [x] Implement IN and NOT IN
    - A `None` among the values is lifted into an `IS NULL` branch, since
      comparing with null inside `IN` matches nothing
  - [x] Implement BETWEEN
  - [x] Implement the pattern matches (LIKE / ILIKE / starts / ends / contains)
  - [x] Implement CASE, the portable way to use a condition as a value
  - [ ] Implement EXISTS / NOT EXISTS over a subquery
  - [ ] Implement IN over a subquery (`IN (SELECT ...)`)
    - Today `is_in` takes a list of values, not a select
- [x] Ordering expressions (OrderingColumnUnit)
  - [x] Sort ascending or descending
  - [x] Place the nulls first or last
- [x] Window expressions (WindowFunctionUnit, AggregateColumnUnit)
  - [x] Attach an OVER clause with PARTITION BY, ORDER BY and a ROWS frame
  - [x] Implement LAG and LEAD
  - [ ] Implement FIRST_VALUE / LAST_VALUE / NTH_VALUE
  - [ ] Implement the RANGE and GROUPS frames
    - Only a ROWS frame is expressible today
- [x] Context-free functions (OperandUnit)
  - [x] Implement the ranking functions (ROW_NUMBER / RANK / DENSE_RANK / NTILE
        / PERCENT_RANK / CUME_DIST)
  - [x] Implement COUNT(*)
  - [x] Implement the session functions (CURRENT_DATE / CURRENT_TIME /
        CURRENT_TIMESTAMP / CURRENT_USER / SESSION_USER)
    - Each raises when compiled for a dialect that lacks it, rather than
      rendering SQL the server will reject
  - [x] Render a raw SQL token as a value expression
    - The keywords a function takes unquoted, like the `day` of
      `DATEADD(day, 7, col)`; bound parameters cannot carry them
  - [x] Implement a plain Python literal into a value expression
    - Turns a literal into a `ColumnUnit`, so an expression can start from a
      value instead of a column and reach the unit methods; the value is bound
      as a parameter, unlike the raw token above

## DQL — Data Query Language

- [x] SELECT (SelectBuilder)
  - [x] Implement a WHERE clause
  - [x] Implement the JOIN clauses
    - [x] Implement RIGHT JOIN
      - SQLAlchemy does not implement RIGHT JOIN (not all dialects has RIGHT
        JOIN)
    - [ ] Add a join guard
      - MySQL and MariaDB have no `FULL OUTER JOIN`, but the clause still
        compiles and only fails at the server
  - [x] Implement a GROUP BY clause
  - [x] Implement a HAVING clause
  - [x] Implement an ORDER BY clause
  - [x] Implement SELECT DISTINCT
  - [x] Implement a row limit
    - Each dialect renders its own form (`TOP` / `LIMIT` / `FETCH NEXT`)
  - [x] Implement a row offset
  - [x] Implement page-at-a-time reads
    - Sets the limit and the offset together from a 1-based page number
  - [x] Expose a select as a scalar subquery value
  - [x] Expose a select as a named derived table
- [ ] Implement CTEs (`WITH`)
- [ ] Implement the set operations (`UNION` / `INTERSECT` / `EXCEPT`)

## DML — Data Manipulation Language

- [x] INSERT (InsertBuilder)
  - [x] Insert a row from explicit column values
  - [x] Insert every row of a DataFrame
  - [x] Insert the rows a SELECT produces (`INSERT INTO ... SELECT`)
  - [x] Report the values the statement will bind
  - [x] Split a large insert into chunked statements
    - Each statement carries as many rows as the dialect's row cap and parameter
      budget allow
  - [x] Return the inserted rows
    - `returning()` renders `RETURNING`, or `OUTPUT inserted.*` on MSSQL; a
      DataFrame insert then runs as the chunked multi-row statements
- [x] UPDATE (UpdateBuilder)
  - [x] Assign the new column values
  - [x] Restrict the updated rows with a WHERE clause
  - [x] Return the updated rows
    - `returning()` renders `RETURNING`, or `OUTPUT inserted.*` on MSSQL
  - [ ] Update against a joined source (`UPDATE ... FROM`)
- [x] DELETE (DeleteBuilder)
  - [x] Restrict the deleted rows with a WHERE clause
  - [x] Return the deleted rows
    - `returning()` renders `RETURNING`, or `OUTPUT deleted.*` on MSSQL
  - [ ] Delete against a joined source (`USING` / `DELETE ... FROM`)
- [x] CALL / EXEC (CallableUnit)
  - [x] Render the dialect's `CALL` / `EXEC` statement
  - [x] Compile the call into a `SQL` for the engine handler
  - [x] Execute the call and collect its rows
  - [ ] Pass the arguments by name
    - Only positional arguments are accepted today
  - [ ] Read OUT / INOUT parameters back
- [ ] Implement MERGE / UPSERT
  - Dialect-divergent; needs its own builder

Notes on returning:

1. MSSQL, PostgreSQL, SQLite and MariaDB compile to a clause the current
   execution path can read. MySQL and Oracle cannot.
2. SQLAlchemy will not raise on our behalf. Every dialect carries an
   `insert_returning` flag, but only the ORM reads it — the compiler never does,
   so it renders the clause on a backend that has none and the error only
   surfaces at the server:

       # mysql dialect, insert_returning = False
       sa.insert(items).returning(items.c.id)
       INSERT INTO items (id) VALUES (:id) RETURNING items.id

   The builder therefore has to check the dialect and raise first, the way
   `_compiler.py` does for functions like `CURRENT_DATE` on MSSQL.

3. MariaDB compiles correctly as it is; no `@compiles` override is needed. Its
   flag is misleading rather than accurate: the dialect `DialectMap.sa_dialect`
   builds has never connected, and MariaDB only learns its own version — and
   sets the flag from it — during `initialize()` on first connect. Real support
   is INSERT from 10.5 and DELETE from 10.0.5; `UPDATE ... RETURNING` does not
   exist.
4. Oracle returns nothing to fetch. `RETURNING id INTO :ret_0` hands the values
   back through bind variables the caller allocates, one entry per affected row:

       out_id = cursor.var(oracledb.DB_TYPE_NUMBER)
       cursor.execute("INSERT INTO items (name) VALUES (:name)"
                      " RETURNING id INTO :out_id", name="bolt", out_id=out_id)
       out_id.getvalue()   # [7]

   Supporting it means `SQL` marking which parameters are OUT and
   `EngineHandler` reading them back instead of calling `result.fetchall()`.

5. A returning INSERT has to come from `to_sqls`, not `to_sql`. For a DataFrame
   insert `to_sql` emits one single-row statement plus one record per row, which
   the driver runs once per record. PEP 249 leaves an execute-many over a
   row-returning statement undefined, so the values are unreachable there —
   sqlite3 rejects the call outright with
   `InterfaceError: bad parameter or other API misuse`:

       INSERT INTO items (id, name) VALUES (:id, :name)
       [{"id": 1, ...}, {"id": 2, ...}, {"id": 3, ...}]    -- 3 executions

   `to_sqls` folds the same rows into the `VALUES` clause itself, so a chunk is
   one ordinary execute whose rows can be fetched:

       INSERT INTO items (id, name)
       VALUES (:id_m0, :name_m0), (:id_m1, :name_m1), (:id_m2, :name_m2)
       {"id_m0": 1, "name_m0": ...}                        -- 1 execution

Resolution: each of the three builders takes a `returning(*columns)` — every
column of the target when none are named — and the rows arrive in the
DataFrame `run` already returns, since `EngineHandler` collects whatever the
result carries.

Which dialects may ask is `DialectMap.returning`, a `ReturningSupport` per
statement kind: all three on MSSQL, PostgreSQL and SQLite, INSERT and DELETE on
MariaDB, none on MySQL and Oracle. `returning()` raises there rather than
compiling a clause the server would reject, which covers notes 1 to 4; Oracle's
OUT-variable route stays unimplemented.

Note 5 is handled inside `InsertBuilder`: a returning DataFrame insert runs
through `to_sqls` whatever `chunk_size` says, its chunks' frames concatenated
into one, and `to_sql` raises instead of binding a record per execution.
`render` shows the first chunked statement there, which is the form that runs.

## DDL — Data Definition Language

- [x] CREATE temporary table (TempBuilder)
  - [x] Clone an object unit's columns into a temp table
  - [x] Choose which database-generated columns the clone keeps
    - STAGE / STAGE_WITH_DEFAULTS / FULL
  - [x] Build the temp table from a DataFrame's inferred dtypes
  - [x] Create a global temporary table
    - Named with `##` on MSSQL, inherent on Oracle, rejected on the other
      dialects
  - [x] Expose the temp table as an object unit
  - [ ] Create indexes on the staged table
    - A staged join key is unindexed today
- [x] TRUNCATE (TruncateBuilder)
  - [x] Empty a table
    - Rendered as `DELETE FROM` on SQLite, which has no `TRUNCATE`
  - [ ] Reset the identity counter and cascade to referencing tables
- [ ] Implement CREATE for persistent objects
- [ ] Implement ALTER
- [ ] Implement DROP
- [ ] Implement RENAME
- [ ] Generate migrations from a schema diff
  - Diff the generated models against the live schema

Note: CREATE, ALTER, DROP and RENAME must also update the active database model
in the current repo, keeping the generated models in sync with the schema they
change.

## TCL — Transaction Control Language

Managed by the library, not exposed as user statements.

- [x] Auto commit / rollback per statement (EngineHandler.run_sql)
- [x] All-or-nothing multi-statement transaction (EngineHandler.run_sqls)
- [x] Scoped transaction for compound ops (engine.begin())

User-facing BEGIN / COMMIT / ROLLBACK / SAVEPOINT are out of scope — the library
owns transaction boundaries.

## DCL — Data Control Language

GRANT / REVOKE / DENY will not be implemented. Privilege management is an
administrative concern, usually done once by a DBA through migration or
infrastructure tooling rather than at application runtime. Exposing it here
would also mean the application's connection holds the right to grant
privileges, which works against least-privilege. It is also highly
dialect-divergent (object vs column vs schema/role grants, roles,
`WITH GRANT OPTION`, MSSQL `DENY`, Oracle system vs object privileges).

## Open questions

Decisions to be made later about scope and direction.

- Should the library support async execution (async engine/session), or stay
  sync-only?
- Should SELECT results support streaming / chunked reads for large result sets,
  instead of always materializing a full DataFrame?
- Should connections retry automatically on transient/dropped-connection
  failures?
- Should model generation be exposed through a CLI?
- Should the library adopt object-graph ORM features (identity map, unit of
  work, relationship navigation, lazy/eager loading), or stay with DataFrames
  and explicit joins?
