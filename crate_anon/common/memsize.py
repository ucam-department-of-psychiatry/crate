"""
crate_anon/common/memsize.py

===============================================================================

    Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

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
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

===============================================================================

Calculate the size of objects in memory (fast).

From https://stackoverflow.com/questions/449560/how-do-i-determine-the-size-of-an-object-in-python

"""  # noqa: E501

from gc import get_referents
from sys import getsizeof
from types import ModuleType, FunctionType
from typing import Any, List, Set

# Custom objects know their class.
# Function objects seem to know way too much, including modules.
# Exclude modules as well.
DENYLIST = type, ModuleType, FunctionType


def getsize(obj: Any, assume_none_denied: bool = False) -> int:
    """
    Return the total size (in bytes) of the object and its members.
    From https://stackoverflow.com/questions/449560/how-do-i-determine-the-size-of-an-object-in-python

    Args:
        obj:
            Object to check.
        assume_none_denied:
            Skip checks for classes/modules/functions. Assume that all objects
            should be checked (typically, meaning that the caller guarantees
            not to pass stuff that doesn't need checking).
    """  # noqa: E501
    if not assume_none_denied:
        if isinstance(obj, DENYLIST):
            raise TypeError(
                f"getsize() does not take argument of type: " f"{type(obj)}"
            )
    seen_ids = set()  # type: Set[int]
    size = 0
    objects = [obj]  # type: List[Any]
    while objects:
        need_referents = []  # type: List[Any]
        for obj in objects:
            if assume_none_denied or not isinstance(obj, DENYLIST):
                obj_id = id(obj)
                if obj_id not in seen_ids:
                    seen_ids.add(obj_id)
                    size += getsizeof(obj)
                    need_referents.append(obj)
        objects = get_referents(*need_referents)
    return size
