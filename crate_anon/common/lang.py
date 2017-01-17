#!/usr/bin/env python
# crate_anon/common/lang.py

"""
===============================================================================
    Copyright © 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

    This file is part of CRATE.

    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.
===============================================================================
"""

# from enum import Enum
from typing import Any, Dict, Optional


def get_case_insensitive_dict_key(d: Dict, k: str) -> Optional[str]:
    for key in d.keys():
        if k.lower() == key.lower():
            return key
    return None


def rename_kwarg(kwargs: Dict[str, Any], old: str, new: str) -> None:
    kwargs[new] = kwargs.pop(old)
