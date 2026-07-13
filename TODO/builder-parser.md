# Inspector reflection support across dialects

Reference for which `sqlalchemy.Inspector` methods used by
`_model_def/_extractor.py` are implemented per dialect, verified against
**SQLAlchemy 2.0.50** installed in this environment.

## Support matrix

| Inspector method         | PostgreSQL | MySQL / MariaDB | SQLite | MSSQL | Oracle |
|--------------------------|:----------:|:---------------:|:------:|:-----:|:------:|
| `get_schema_names`       | yes        | yes             | yes    | yes   | yes    |
| `get_table_names`        | yes        | yes             | yes    | yes   | yes    |
| `get_view_names`         | yes        | yes             | yes    | yes   | yes    |
| `get_columns`            | yes        | yes             | yes    | yes   | yes    |
| `get_pk_constraint`      | yes        | yes             | yes    | yes   | yes    |
| `get_foreign_keys`       | yes        | yes             | yes    | yes   | yes    |
| `get_indexes`            | yes        | yes             | yes    | yes   | yes    |
| `get_unique_constraints` | yes        | yes             | yes    | **NO**| yes    |
| `get_check_constraints`  | yes        | yes             | yes    | **NO**| yes    |
| `get_table_comment`      | yes        | yes             | **NO** | **NO**| yes    |

"NO" = the dialect inherits the base `DefaultDialect` implementation, which
raises `NotImplementedError`.

## Impact in `_extractor.py`

| Call site                                     | Method                   | Status                              |
|-----------------------------------------------|--------------------------|-------------------------------------|
| `list_unique_clusters` (~line 169)            | `get_unique_constraints` | UNGUARDED - crashes on MSSQL        |
| `_get_single_column_uniques` (~line 267)      | `get_unique_constraints` | UNGUARDED - crashes on MSSQL        |
| `list_check_constraints` (~line 221)          | `get_check_constraints`  | guarded (try/except NotImplemented) |
| `_get_comment` (~line 249)                    | `get_table_comment`      | guarded (try/except NotImplemented) |

## Handling option 1 - defensive helper

Wrap the optional calls so an unsupported dialect degrades to empty results
instead of raising. Add a helper and route both unique-constraint calls
through it.

```python
def _get_unique_constraints(self, schema_name: str, object_name: str) -> list[dict[str, Any]]:
    try:
        return self._inspector.get_unique_constraints(object_name, schema=schema_name)
    except NotImplementedError:
        return []
```

Then replace the two direct calls (lines ~169 and ~267):

```python
for constraint in self._get_unique_constraints(schema_name, object_name):
    ...
```

Pros: minimal change, dialect-agnostic, safe.
Cons: on MSSQL you lose unique-constraint metadata from this method (though
unique constraints still surface as unique indexes via `get_indexes`).

## Handling option 2 - raw SQL fallback

When the inspector method is unavailable, query the dialect's system catalog
directly via `self._inspector.bind` (the Connection/Engine).

### MSSQL - unique constraints

```sql
SELECT
    kc.name        AS constraint_name,
    c.name         AS column_name,
    ic.key_ordinal AS ordinal_position
FROM sys.key_constraints kc
JOIN sys.tables       t  ON t.object_id = kc.parent_object_id
JOIN sys.schemas      s  ON s.schema_id = t.schema_id
JOIN sys.index_columns ic ON ic.object_id = kc.parent_object_id
                          AND ic.index_id = kc.unique_index_id
JOIN sys.columns      c  ON c.object_id = ic.object_id
                          AND c.column_id = ic.column_id
WHERE kc.type = 'UQ'
  AND s.name = :schema_name
  AND t.name = :object_name
ORDER BY kc.name, ic.key_ordinal;
```

### MSSQL - check constraints

```sql
SELECT
    cc.name       AS constraint_name,
    cc.definition AS sqltext
FROM sys.check_constraints cc
JOIN sys.tables  t ON t.object_id = cc.parent_object_id
JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE s.name = :schema_name
  AND t.name = :object_name;
```

### MSSQL - table comment (extended property MS_Description)

```sql
SELECT CAST(ep.value AS NVARCHAR(MAX)) AS table_comment
FROM sys.extended_properties ep
JOIN sys.tables  t ON t.object_id = ep.major_id
JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE ep.minor_id = 0
  AND ep.name = 'MS_Description'
  AND s.name = :schema_name
  AND t.name = :object_name;
```

### SQLite - table comment

SQLite has no native table comments; there is no catalog to query. The only
option is to parse the trailing comment in `sqlite_master.sql`, which is
unreliable. Recommendation: treat as always empty on SQLite.

### Example wiring for the raw-SQL fallback

```python
from sqlalchemy import text

def _get_unique_constraints(self, schema_name: str, object_name: str) -> list[dict[str, Any]]:
    try:
        return self._inspector.get_unique_constraints(object_name, schema=schema_name)
    except NotImplementedError:
        return self._unique_constraints_via_sql(schema_name, object_name)

def _unique_constraints_via_sql(self, schema_name: str, object_name: str) -> list[dict[str, Any]]:
    dialect = self._inspector.bind.dialect.name
    if dialect != "mssql":
        return []
    rows = self._inspector.bind.execute(
        text(MSSQL_UNIQUE_SQL),
        {"schema_name": schema_name, "object_name": object_name},
    ).fetchall()
    grouped: dict[str, list[str]] = {}
    for name, column, _ in rows:
        grouped.setdefault(name, []).append(column)
    return [{"name": name, "column_names": cols} for name, cols in grouped.items()]
```

Pros: full metadata even on MSSQL.
Cons: dialect-specific SQL to maintain; must reshape rows into the same dict
shape the inspector returns (`{"name", "column_names"}`).

