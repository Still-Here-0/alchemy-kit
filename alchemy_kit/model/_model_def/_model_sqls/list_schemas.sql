SELECT [name]
FROM sys.schemas
WHERE schema_id < 16384 -- User schemas only
ORDER BY [name]

