SELECT
    cc.name       AS constraint_name,
    cc.definition AS sqltext
FROM sys.check_constraints cc
JOIN sys.tables  t ON t.object_id = cc.parent_object_id
JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE s.name = @schema_name
  AND t.name = @object_name
ORDER BY cc.name
