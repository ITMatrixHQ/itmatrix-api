from __future__ import annotations

from enum import IntEnum, auto


class ReturnType(IntEnum):
    """Client-wide data return conversion mode."""

    STRUCT = auto()
    DATAFRAME = auto()
    ARRAY_DICT = auto()


def normalize_return_type(value: ReturnType | str | int) -> ReturnType:
    """Return a stable enum value from permissive user input."""

    if isinstance(value, ReturnType):
        return value
    if isinstance(value, str):
        aliases = {
            "ARRAYS": ReturnType.ARRAY_DICT,
            "ARRAY_DICT": ReturnType.ARRAY_DICT,
            "DATAFRAME": ReturnType.DATAFRAME,
            "DF": ReturnType.DATAFRAME,
            "DICT": ReturnType.ARRAY_DICT,
            "STRUCT": ReturnType.STRUCT,
            "STRUCTS": ReturnType.STRUCT,
        }
        return aliases[value.upper()]
    return ReturnType(value)
