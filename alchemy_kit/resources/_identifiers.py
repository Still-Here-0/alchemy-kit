import keyword
import builtins

static = set(keyword.kwlist) | set(keyword.softkwlist) | set(dir(builtins)) | {
    "to_model", "Meta", "Config", "BaseModel", "datetime", "date", "Series", "Optional", 
    "Any", "Decimal", "pa", "validate", "init", "strip_timezone", "_get_model_attrs"
}

