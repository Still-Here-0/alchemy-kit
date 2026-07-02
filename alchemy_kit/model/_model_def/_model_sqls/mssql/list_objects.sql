SELECT
  t.name    object_name,
  'Table'   object_type
FROM sys.tables t
JOIN sys.schemas s
  ON s.schema_id = t.schema_id
WHERE s.name = :schema
!t_include_objects!
!t_exclude_objects!

UNION

SELECT
  v.name    object_name,
  'View'    object_type
FROM sys.views v
JOIN sys.schemas s
  ON s.schema_id = v.schema_id
WHERE s.name = :schema
!v_include_objects!
!v_exclude_objects!

ORDER BY object_name

