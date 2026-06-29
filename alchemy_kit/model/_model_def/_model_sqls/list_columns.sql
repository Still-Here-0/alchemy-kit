SELECT
    c.name AS column_name,
    t.name AS sql_type,
    c.is_nullable,
    c.is_identity,
    c.is_computed,
    c.max_length,
    c.precision,
    c.scale,
    c.collation_name,
    CAST(CASE WHEN c.default_object_id <> 0 THEN 1 ELSE 0 END AS bit) AS has_default,
    dc.definition AS default_value,
    CAST(CASE WHEN EXISTS (
        SELECT 1
        FROM sys.index_columns ic
        JOIN sys.indexes i
            ON i.object_id = ic.object_id AND i.index_id = ic.index_id
        WHERE ic.object_id = c.object_id
          AND ic.column_id = c.column_id
          AND ic.is_included_column = 0
          AND i.is_unique = 1
          AND i.is_primary_key = 0
          AND (
              SELECT COUNT(*)
              FROM sys.index_columns ic2
              WHERE ic2.object_id = i.object_id
                AND ic2.index_id = i.index_id
                AND ic2.is_included_column = 0
          ) = 1
    ) THEN 1 ELSE 0 END AS bit) AS is_unique,
    CAST(CASE WHEN EXISTS (
        SELECT 1
        FROM sys.index_columns ic
        JOIN sys.indexes i
            ON i.object_id = ic.object_id AND i.index_id = ic.index_id
        WHERE ic.object_id = c.object_id
          AND ic.column_id = c.column_id
          AND i.is_primary_key = 1
    ) THEN 1 ELSE 0 END AS bit) AS is_primary_key,
    CAST(CASE WHEN EXISTS (
        SELECT 1
        FROM sys.foreign_key_columns fkc
        WHERE fkc.parent_object_id = c.object_id
          AND fkc.parent_column_id = c.column_id
    ) THEN 1 ELSE 0 END AS bit) AS is_foreign_key,
    fk.fk_ref_schema,
    fk.fk_ref_table,
    fk.fk_ref_column,
    CAST(ep.value AS NVARCHAR(MAX)) AS description
FROM sys.columns c
JOIN sys.objects o ON o.object_id = c.object_id
JOIN sys.schemas s ON s.schema_id = o.schema_id
JOIN sys.types t ON t.user_type_id = c.user_type_id
LEFT JOIN sys.default_constraints dc
    ON dc.object_id = c.default_object_id
OUTER APPLY (
    SELECT TOP 1
        ref_s.name AS fk_ref_schema,
        ref_o.name AS fk_ref_table,
        ref_c.name AS fk_ref_column
    FROM sys.foreign_key_columns fkc
    JOIN sys.objects ref_o ON ref_o.object_id = fkc.referenced_object_id
    JOIN sys.schemas ref_s ON ref_s.schema_id = ref_o.schema_id
    JOIN sys.columns ref_c
        ON ref_c.object_id = fkc.referenced_object_id
        AND ref_c.column_id = fkc.referenced_column_id
    WHERE fkc.parent_object_id = c.object_id
      AND fkc.parent_column_id = c.column_id
) fk
LEFT JOIN sys.extended_properties ep
    ON ep.major_id = c.object_id
    AND ep.minor_id = c.column_id
    AND ep.name = 'MS_Description'
    AND ep.class = 1
WHERE s.name = :schema AND o.name = :object AND o.type IN ('U', 'V')
ORDER BY c.column_id
