from typing import Literal, TypeAlias

# The Python type names a dialect map may assign to a SQL type. These are
# emitted verbatim as annotations in generated model files, so every name must
# be importable there ("Any" comes from typing, the rest are builtins or
# datetime members).
PyTypeParameters: TypeAlias = Literal[
    "int", "float", "bool", "str", "datetime", "date", "Any",
]
