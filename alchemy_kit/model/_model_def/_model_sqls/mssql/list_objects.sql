SELECT
  t.name    object_name,
  'Table'   object_type,
  CAST(ep.value AS NVARCHAR(MAX)) object_description
FROM sys.tables t
JOIN sys.schemas s
  ON s.schema_id = t.schema_id
LEFT JOIN sys.extended_properties ep
  ON ep.major_id = t.object_id
  AND ep.minor_id = 0
  AND ep.name = 'MS_Description'
  AND ep.class = 1
WHERE s.name = :schema
!t_include_objects!
!t_exclude_objects!

UNION

SELECT
  v.name    object_name,
  'View'    object_type,
  CAST(ep.value AS NVARCHAR(MAX)) object_description
FROM sys.views v
JOIN sys.schemas s
  ON s.schema_id = v.schema_id
LEFT JOIN sys.extended_properties ep
  ON ep.major_id = v.object_id
  AND ep.minor_id = 0
  AND ep.name = 'MS_Description'
  AND ep.class = 1
WHERE s.name = :schema
!v_include_objects!
!v_exclude_objects!

ORDER BY object_name
