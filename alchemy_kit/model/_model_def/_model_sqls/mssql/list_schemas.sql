SELECT [name]
FROM sys.schemas
WHERE schema_id < 16384 -- User schemas only
!include_schema!
!exclude_schema!
ORDER BY [name]

