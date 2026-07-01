SELECT
    fk.name AS fk_name,
    ref_s.name AS ref_schema,
    ref_o.name AS ref_table,
    STRING_AGG(pc.name, ', ') WITHIN GROUP (ORDER BY fkc.constraint_column_id) AS columns,
    STRING_AGG(rc.name, ', ') WITHIN GROUP (ORDER BY fkc.constraint_column_id) AS ref_columns,
    fk.delete_referential_action_desc AS on_delete,
    fk.update_referential_action_desc AS on_update
FROM sys.foreign_keys fk
JOIN sys.objects o ON o.object_id = fk.parent_object_id
JOIN sys.schemas s ON s.schema_id = o.schema_id
JOIN sys.objects ref_o ON ref_o.object_id = fk.referenced_object_id
JOIN sys.schemas ref_s ON ref_s.schema_id = ref_o.schema_id
JOIN sys.foreign_key_columns fkc
    ON fkc.constraint_object_id = fk.object_id
JOIN sys.columns pc
    ON pc.object_id = fkc.parent_object_id
    AND pc.column_id = fkc.parent_column_id
JOIN sys.columns rc
    ON rc.object_id = fkc.referenced_object_id
    AND rc.column_id = fkc.referenced_column_id
WHERE s.name = :schema
  AND o.name = :object
  AND o.type IN ('U', 'V')
GROUP BY
    fk.name,
    ref_s.name,
    ref_o.name,
    fk.delete_referential_action_desc,
    fk.update_referential_action_desc
ORDER BY fk.name
