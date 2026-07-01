SELECT
    cc.name AS check_name,
    cc.definition AS definition,
    col.name AS column_name
FROM sys.check_constraints cc
JOIN sys.objects o ON o.object_id = cc.parent_object_id
JOIN sys.schemas s ON s.schema_id = o.schema_id
LEFT JOIN sys.columns col
    ON col.object_id = cc.parent_object_id
    AND col.column_id = cc.parent_column_id
WHERE s.name = :schema
  AND o.name = :object
  AND o.type IN ('U', 'V')
ORDER BY cc.name
