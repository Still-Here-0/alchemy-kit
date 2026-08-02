from typing import Any

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql import sqltypes
from sqlalchemy.sql.functions import FunctionElement

from .dialect_map import DialectMap


def _register_render(element: type[FunctionElement[Any]], dialect: type[DialectMap[Any]], rendered: str) -> None:
    @compiles(element, dialect.name)
    def _render(el: Any, compiler: Any, **kw: Any) -> str:
        return rendered


def _register_raise(element: type[FunctionElement[Any]], dialect: type[DialectMap[Any]], name: str) -> None:
    @compiles(element, dialect.name)
    def _raise(el: Any, compiler: Any, **kw: Any) -> str:
        raise ValueError(f"Dialect '{dialect.name}' does not support {name}")


def new_sql_type(
    clsname: str,
    ansi: str,
    sa_return_type: sqltypes.TypeEngine[Any],
    *,
    unsupported: tuple[type[DialectMap[Any]], ...] = (),
    overrides: dict[type[DialectMap[Any]], str] | None = None,
) -> type[FunctionElement[Any]]:
    element = type(clsname, (FunctionElement,), {"inherit_cache": True, "type": sa_return_type})

    @compiles(element)
    def _default(el: Any, compiler: Any, **kw: Any) -> str:
        return ansi

    for dialect in unsupported:
        _register_raise(element, dialect, ansi)
    for dialect, rendered in (overrides or {}).items():
        _register_render(element, dialect, rendered)

    return element
