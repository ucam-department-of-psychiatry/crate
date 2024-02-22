"""
crate_anon/common/stringfunc.py

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

**Simple string functions.**

"""

import fnmatch
from functools import lru_cache
import sys
from typing import Any, List, Optional, Pattern, TextIO, Type

from cardinal_pythonlib.extract_text import wordwrap
import prettytable
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
    return "".join(s.split())


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


def uprint(
    *objects: Any, sep: str = " ", end: str = "\n", file: TextIO = sys.stdout
) -> None:
    """
    Prints strings to outputs that support UTF-8 encoding, but also to those
    that do not (e.g. Windows stdout, sometimes).

    Args:
        *objects: things to print
        sep: separator between those objects
        end: print this at the end
        file: file-like object to print to

    See
    https://stackoverflow.com/questions/14630288/unicodeencodeerror-charmap-codec-cant-encode-character-maps-to-undefined

    Examples:

    - Linux, Python 3.6.8 console: ``sys.stdout.encoding == "UTF-8"``
    - Windows, Python 3.7.4 console: ``sys.stdout.encoding == "utf-8"``
    - Windows, Python 3.7.4, from script: ``sys.stdout.encoding == "cp1252"``
    """  # noqa
    enc = file.encoding.lower()
    if enc == "utf-8":
        print(*objects, sep=sep, end=end, file=file)
    else:

        def f(obj: Any) -> str:
            return str(obj).encode(enc, errors="backslashreplace").decode(enc)

        # https://docs.python.org/3.5/library/codecs.html#codec-base-classes
        print(*map(f, objects), sep=sep, end=end, file=file)


# =============================================================================
# String tests
# =============================================================================


def does_text_contain_word_chars(text: str) -> bool:
    """
    Is a string worth treating as interesting text -- does it contain "word"
    characters?
    """
    # Slower (as per FS's tests):
    #   regex_any_word_char = regex.compile(r'[\w\W]*[a-zA-Z0-9_][\w\W]*')
    #   return bool(text and regex_any_word_char.match(text))
    # Faster:
    return bool(text and any(33 <= ord(c) <= 126 for c in text))


# =============================================================================
# Docstring manipulation
# =============================================================================


def get_docstring(cls: Type) -> str:
    """
    Fetches a docstring from a class.
    """
    # PyCharm thinks that __doc__ is bytes, but it's str!
    # ... ah, no, now it's stopped believing that.
    return cls.__doc__ or ""
    # This is likely unnecessary: even integer variables have the __doc__
    # attribute.
    # return getattr(cls, '__doc__', "") or ""


def compress_docstring(docstring: str) -> str:
    """
    Splats a docstring onto a single line, compressing all whitespace.
    """
    docstring = docstring.replace("\n", " ")
    # https://stackoverflow.com/questions/2077897/substitute-multiple-whitespace-with-single-whitespace-in-python
    return " ".join(docstring.split())


def trim_docstring(docstring: str) -> str:
    """
    Removes initial/terminal blank lines and leading whitespace from
    docstrings.

    This is the PEP257 implementation (https://peps.python.org/pep-0257/),
    except with ``sys.maxint`` replaced by ``sys.maxsize`` (see
    https://docs.python.org/3.1/whatsnew/3.0.html#integers).

    Demonstration:

    .. code-block:: python

        from crate_anon.common.stringfunc import trim_docstring
        print(trim_docstring.__doc__)
        print(trim_docstring(trim_docstring.__doc__))
    """
    if not docstring:
        return ""
    # Convert tabs to spaces (following the normal Python rules)
    # and split into a list of lines:
    lines = docstring.expandtabs().splitlines()
    # Determine minimum indentation (first line doesn't count):
    indent = sys.maxsize
    for line in lines[1:]:
        stripped = line.lstrip()
        if stripped:
            indent = min(indent, len(line) - len(stripped))
    # Remove indentation (first line is special):
    trimmed = [lines[0].strip()]
    if indent < sys.maxsize:
        for line in lines[1:]:
            trimmed.append(line[indent:].rstrip())
    # Strip off trailing and leading blank lines:
    while trimmed and not trimmed[-1]:
        trimmed.pop()
    while trimmed and not trimmed[0]:
        trimmed.pop(0)
    # Return a single string:
    return "\n".join(trimmed)


# =============================================================================
# Tabular
# =============================================================================


def make_twocol_table(
    colnames: List[str],
    rows: List[List[str]],
    max_table_width: int = 79,
    padding_width: int = 1,
    vertical_lines: bool = True,
    rewrap_right_col: bool = True,
) -> str:
    """
    Formats a two-column table. Tries not to split/wrap the left-hand column,
    but resizes the right-hand column.
    """
    leftcol_width = max(len(r[0]) for r in [colnames] + rows)
    pt = prettytable.PrettyTable(
        colnames,
        header=True,
        border=True,
        hrules=prettytable.ALL,
        vrules=prettytable.ALL if vertical_lines else prettytable.NONE,
        align="l",  # default alignment for all columns (left)
        valign="t",  # default alignment for all rows (top)
        max_table_width=max_table_width,
        padding_width=padding_width,
    )
    rightcol_width = max_table_width - leftcol_width - (4 * padding_width) - 3
    # ... 3 vertical lines (even if invisible); 4 paddings (2 per column)
    pt.max_width[colnames[0]] = leftcol_width
    pt.max_width[colnames[1]] = rightcol_width
    for row in rows:
        righttext = row[1]
        if rewrap_right_col:
            righttext = wordwrap(righttext, width=rightcol_width)
        ptrow = [row[0], righttext]
        pt.add_row(ptrow)
    return pt.get_string()


# =============================================================================
# Checking strings for NLP
# =============================================================================

_RELEVANT_FOR_NLP_REGEX_STR = r"\w"  # word character present
RELEVANT_FOR_NLP_REGEX = regex.compile(
    _RELEVANT_FOR_NLP_REGEX_STR, flags=regex.IGNORECASE
)
# regex deals with Unicode automatically, as verified in stringfunc_tests.py


def relevant_for_nlp(x: Optional[str]) -> bool:
    """
    Does this string contain content that's relevant for NLP?
    We want to eliminate ``None`` values, and strings that do not contain
    relevant content. A string containing only whitespace is not relevant.
    """
    if not x:
        # None, or empty string
        return False
    return RELEVANT_FOR_NLP_REGEX.search(x) is not None
