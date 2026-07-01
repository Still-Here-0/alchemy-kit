SELECT
    i.name AS key_name,
    i.is_primary_key,
    i.is_unique_constraint,
    i.is_unique,
    i.type_desc AS index_type,
    COUNT(*) AS column_count,
    STRING_AGG(c.name, ', ') WITHIN GROUP (ORDER BY ic.key_ordinal) AS columns
FROM sys.indexes i
JOIN sys.objects o ON o.object_id = i.object_id
JOIN sys.schemas s ON s.schema_id = o.schema_id
JOIN sys.index_columns ic
    ON ic.object_id = i.object_id
    AND ic.index_id = i.index_id
    AND ic.is_included_column = 0
JOIN sys.columns c
    ON c.object_id = ic.object_id
    AND c.column_id = ic.column_id
WHERE s.name = :schema
  AND o.name = :object
  AND o.type IN ('U', 'V')
  AND (i.is_primary_key = 1 OR i.is_unique = 1)
GROUP BY i.name, i.index_id, i.is_primary_key, i.is_unique_constraint, i.is_unique, i.type_desc
HAVING COUNT(*) > 1
ORDER BY i.is_primary_key DESC, i.is_unique_constraint DESC, i.name
