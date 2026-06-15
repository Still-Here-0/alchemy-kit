from typing import Literal, Union, Any, get_args, get_origin

def flatten_literal_args(tp: Any) -> tuple:
    if get_origin(tp) is Union:
        return sum((flatten_literal_args(t) for t in get_args(tp)), ())
    if get_origin(tp) is Literal:
        return get_args(tp)
    return ()


def check_literal(input: str, types: Any) -> bool:
    return input in flatten_literal_args(types)
