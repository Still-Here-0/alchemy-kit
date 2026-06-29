SELECT
  t.name    object_name,
  'Table'   object_type
FROM sys.tables t
JOIN sys.schemas s
  ON s.schema_id = t.schema_id
WHERE s.name = :schame
!table_scripts!

UNION

SELECT
  v.name    object_name,
  'View'    object_type
FROM sys.views v
JOIN sys.schemas s
  ON s.schema_id = v.schema_id
WHERE s.name = :schame
!view_scripts!

ORDER BY object_name

