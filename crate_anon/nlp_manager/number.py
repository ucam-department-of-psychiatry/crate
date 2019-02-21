#!/usr/bin/env python

"""
crate_anon/nlp_manager/number.py

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

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

**Number conversion functions.**

"""

from typing import Optional


def to_float(s: str) -> Optional[float]:
    """
    Convert a string to a float, or return ``None``.

    Before converting:

    - strips out commas (as thousands separator); this is not internationalized
      well!
    - replace Unicode minus and en dash with a hyphen (minus sign)
    """
    if s:
        s = s.replace(',', '')  # comma as thousands separator
        s = s.replace('−', '-')  # Unicode minus
        s = s.replace('–', '-')  # en dash
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def to_pos_float(s: str) -> Optional[float]:
    """
    Converts a string to a positive float, by using :func:`to_float` followed
    by :func:`abs`. Returns ``None`` on failure.
    """
    try:
        return abs(to_float(s))
    except TypeError:  # to_float() returned None
        return None
