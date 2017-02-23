#!/usr/bin/env python
# crate_anon/nlp_manager/text_handling.py

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

import logging
from typing import Dict
from cardinal_pythonlib.rnc_lang import chunks

log = logging.getLogger(__name__)


# =============================================================================
# Input support methods
# =============================================================================

def tsv_pairs_to_dict(line: str, key_lower: bool = True) -> Dict[str, str]:
    """
    Converts a TSV line into sequential key/value pairs as a dictionary.
    """
    items = line.split("\t")
    d = {}  # type: Dict[str, str]
    for chunk in chunks(items, 2):
        if len(chunk) < 2:
            log.warning("Bad chunk, not of length 2: {}".format(repr(chunk)))
            continue
        key = chunk[0]
        value = unescape_tabs_newlines(chunk[1])
        if key_lower:
            key = key.lower()
        d[key] = value
    return d


def escape_tabs_newlines(s: str) -> str:
    """
    Escapes CR, LF, tab, and backslashes. (Here just for testing; mirrors the
    equivalent function in the Java code.)
    """
    if not s:
        return s
    s = s.replace("\\", r"\\")  # replace \ with \\
    s = s.replace("\n", r"\n")  # escape \n; note ord("\n") == 10
    s = s.replace("\r", r"\r")  # escape \r; note ord("\r") == 13
    s = s.replace("\t", r"\t")  # escape \t; note ord("\t") == 9
    return s


def unescape_tabs_newlines(s: str) -> str:
    """
    Reverses escape_tabs_newlines.
    """
    # See also http://stackoverflow.com/questions/4020539
    if not s:
        return s
    d = ""  # the destination string
    in_escape = False
    for i in range(len(s)):
        c = s[i]  # the character being processed
        if in_escape:
            if c == "r":
                d += "\r"
            elif c == "n":
                d += "\n"
            elif c == "t":
                d += "\t"
            else:
                d += c
            in_escape = False
        else:
            if c == "\\":
                in_escape = True
            else:
                d += c
    return d
