#!/usr/bin/env python
# crate_anon/common/lang.py

# from enum import Enum
from typing import Any, Dict, Optional


def get_case_insensitive_dict_key(d: Dict, k: str) -> Optional[str]:
    for key in d.keys():
        if k.lower() == key.lower():
            return key
    return None


def rename_kwarg(kwargs: Dict[str, Any], old: str, new: str) -> None:
    kwargs[new] = kwargs.pop(old)
