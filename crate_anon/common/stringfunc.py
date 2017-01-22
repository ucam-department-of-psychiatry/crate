#!/usr/bin/env python
# crate_anon/common/stringfunc.py

"""
===============================================================================
    Copyright (C) 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

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

import re
from typing import Dict, Iterable, List


# =============================================================================
# Replacement
# =============================================================================

def multiple_replace(text: str, rep: Dict[str, str]) -> str:
    """Returns text in which the keys of rep (a dict) have been replaced by
    their values."""
    # http://stackoverflow.com/questions/6116978/python-replace-multiple-strings  # noqa
    rep = dict((re.escape(k), v) for k, v in rep.items())
    pattern = re.compile("|".join(rep.keys()))
    return pattern.sub(lambda m: rep[re.escape(m.group(0))], text)


def replace_in_list(stringlist: Iterable[str],
                    replacedict: Dict[str, str]) -> List[str]:
    newlist = []
    for fromstring in stringlist:
        newlist.append(multiple_replace(fromstring, replacedict))
    return newlist


# =============================================================================
# Simple string manipulation
# =============================================================================

def get_digit_string_from_vaguely_numeric_string(s: str) -> str:
    """
    Strips non-digit characters from a string.
    For example, converts "(01223) 123456" to "01223123456".
    """
    return "".join([d for d in s if d.isdigit()])


def reduce_to_alphanumeric(s: str) -> str:
    """
    Strips non-alphanumeric characters from a string.
    For example, converts "PE12 3AB" to "PE12 3AB".
    """
    return "".join([d for d in s if d.isalnum()])


def remove_whitespace(s: str) -> str:
    """
    Removes whitespace from a string.
    """
    return ''.join(s.split())
