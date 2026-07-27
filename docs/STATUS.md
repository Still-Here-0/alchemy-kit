# Project Status

What alchemy-kit implements today and what remains. Checked items are done;
unchecked items are planned.

Last updated: 2026-07-26

The user drives DQL, DML and DDL through builders. The library owns TCL
internally (it manages transaction boundaries). DCL will not be implemented.

## DQL — Data Query Language

- [x] SELECT (SelectBuilder)
    - [x] where
    - [x] join
    - [x] group_by
    - [x] having
    - [x] order_by
    - [x] distinct
    - [x] limit
    - [x] offset
    - [x] paginate
    - [x] as_scalar
    - [x] as_object

## DML — Data Manipulation Language

- [x] INSERT (InsertBuilder: from_values, from_dataframe, from_select, chunked run)
- [x] UPDATE (UpdateBuilder: set_values, where)
- [x] DELETE (DeleteBuilder: where)
- [x] CALL / EXEC (CallableUnit: render, to_sql, run)
- [ ] MERGE / UPSERT (dialect-divergent; needs its own builder)

## DDL — Data Definition Language

- [x] Schema reflection to model generation (reads existing DDL)
- [x] CREATE temporary table (TempBuilder.from_dataframe)
- [x] TRUNCATE (TruncateBuilder)
- [ ] CREATE (persistent objects)
- [ ] ALTER
- [ ] DROP
- [ ] RENAME

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
