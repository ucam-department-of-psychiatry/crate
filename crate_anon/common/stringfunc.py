#!/usr/bin/env python

"""
crate_anon/common/stringfunc.py

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

**Simple string functions.**

"""

import fnmatch
from functools import lru_cache
import sys
from typing import Any, Pattern, TextIO

import regex


# =============================================================================
# Simple string manipulation
# =============================================================================

def get_digit_string_from_vaguely_numeric_string(s: str) -> str:
    """
    Strips non-digit characters from a string.

    For example, converts ``"(01223) 123456"`` to ``"01223123456"``.
    """
    return "".join([d for d in s if d.isdigit()])


def reduce_to_alphanumeric(s: str) -> str:
    """
    Strips non-alphanumeric characters from a string.

    For example, converts ``"PE12 3AB"`` to ``"PE12 3AB"``.
    """
    return "".join([d for d in s if d.isalnum()])


def remove_whitespace(s: str) -> str:
    """
    Removes whitespace from a string.
    """
    return ''.join(s.split())


# =============================================================================
# Specification matching
# =============================================================================

@lru_cache(maxsize=None)
def get_spec_match_regex(spec: str) -> Pattern:
    """
    Returns a compiled, case-insensitive regular expression representing a
    shell-style pattern (using ``*``, ``?`` and similar wildcards; see
    https://docs.python.org/3.5/library/fnmatch.html).

    Args:
        spec: the pattern to pass to ``fnmatch``, e.g. ``"patient_addr*"``.

    Returns:
        the compiled regular expression
    """
    return regex.compile(fnmatch.translate(spec), regex.IGNORECASE)


# =============================================================================
# Printing/encoding
# =============================================================================

def uprint(*objects: Any,
           sep: str = ' ',
           end: str = '\n',
           file: TextIO = sys.stdout) -> None:
    """
    Prints strings to outputs that support UTF-8 encoding, but also to those
    that do not (e.g. Windows stdout).

    Args:
        *objects: things to print
        sep: separator between those objects
        end: print this at the end
        file: file-like object to print to

    See
    http://stackoverflow.com/questions/14630288/unicodeencodeerror-charmap-codec-cant-encode-character-maps-to-undefined
    """  # noqa
    enc = file.encoding
    if enc == 'UTF-8':
        print(*objects, sep=sep, end=end, file=file)
    else:
        def f(obj):
            return str(obj).encode(enc, errors='backslashreplace').decode(enc)
        # https://docs.python.org/3.5/library/codecs.html#codec-base-classes
        print(*map(f, objects), sep=sep, end=end, file=file)
