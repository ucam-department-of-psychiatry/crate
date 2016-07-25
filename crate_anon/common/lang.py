#!/usr/bin/env python
# crate_anon/common/lang.py

from enum import Enum
from typing import Any, Dict, Optional


def merge_two_dicts(x: Dict, y: Dict) -> Dict:
    """Given two dicts, merge them into a new dict as a shallow copy."""
    # http://stackoverflow.com/questions/38987
    z = x.copy()
    z.update(y)  # y takes precedence over x
    return z


def get_case_insensitive_dict_key(d: Dict, k: str) -> Optional[str]:
    for key in d.keys():
        if k.lower() == key.lower():
            return key
    return None


STR_ENUM_FWD_REF = "StrEnum"
# class name forward reference for type checker:
# http://mypy.readthedocs.io/en/latest/kinds_of_types.html
# ... but also: a variable (rather than a string literal) stops PyCharm giving
# the curious error "PEP 8: no newline at end of file" and pointing to the
# type hint string literal.


class StrEnum(Enum):
    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def lookup(cls, value: Any) -> Optional[STR_ENUM_FWD_REF]:
        for item in cls:
            if value == item.value:
                return item
        if not value:
            return None
        raise ValueError("Value {} not found in enum class {}".format(
            value, cls.__name__))

    def __lt__(self, other: STR_ENUM_FWD_REF) -> bool:
        return str(self) < str(other)


def rename_kwarg(kwargs: Dict[str, Any], old: str, new: str) -> None:
    kwargs[new] = kwargs.pop(old)
