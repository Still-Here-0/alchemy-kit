class SchemaConfig:
    """Configure which schemas and objects are included or excluded.

    By default every schema and object (e.g. table) is considered included.
    This class lets you narrow or filter that selection in two ways:

    - Include: register specific schemas or objects to explicitly select them.
    - Exclude: register specific schemas or objects to filter them out.

    Both include and exclude rules are stored as a mapping of schema name to a
    set of object names. An empty set for a schema means the rule applies to
    the whole schema rather than a specific list of objects.

    Attributes:
        _include: Mapping of schema name to the set of explicitly included
            object names. An empty set means the entire schema is included.
        _exclude: Mapping of schema name to the set of explicitly excluded
            object names. An empty set means the entire schema is excluded.
    """

    def __init__(self) -> None:
        self._include: dict[str, set[str]] = {}
        self._exclude: dict[str, set[str]] = {}

    def include(self, data: dict[str, set[str]]):
        for schema_name, objects in data.items():
            self.include_objects(schema_name, objects)

    def include_schema(self, name: str):
        if name in self._include.keys():
            return
    
        self._include[name] = set()

    def include_object(self, schema_name: str, object_name: str):
        if schema_name in self._include.keys():
            self._include[schema_name].add(object_name)

        else:
            self._include[schema_name] = set(object_name)

    def include_objects(self, schema_name: str, objects: set[str]):
        if schema_name not in self._include.keys():
            self._include[schema_name] = objects
            return

        else:
            self._include[schema_name].update(objects)

    def exclude(self, data: dict[str, set[str]]):
        for schema_name, objects in data.items():
            self.exclude_objects(schema_name, objects)

    def exclude_schema(self, name: str):
        if name in self._exclude.keys():
            return
    
        self._exclude[name] = set()

    def exclude_object(self, schema_name: str, object_name: str):
        if schema_name in self._exclude.keys():
            self._exclude[schema_name].add(object_name)

        else:
            self._exclude[schema_name] = set(object_name)

    def exclude_objects(self, schema_name: str, objects: set[str]):
        if schema_name not in self._exclude.keys():
            self._exclude[schema_name] = objects
            return

        else:
            self._exclude[schema_name].update(objects)

