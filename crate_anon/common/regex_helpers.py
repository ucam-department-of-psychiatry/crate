#!/usr/bin/env python

"""
crate_anon/common/regex_helpers.py

===============================================================================

    Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).

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

**Constants and helper functionsfor use with regexes.**

"""

from typing import Iterable, List, Union

import regex  # sudo apt-get install python-regex


# =============================================================================
# Constants
# =============================================================================

# Reminders: ? zero or one, + one or more, * zero or more
# Non-capturing groups: (?:...)
# ... https://docs.python.org/3/howto/regex.html
# ... https://stackoverflow.com/questions/3512471/non-capturing-group

ASTERISK = r"\*"
AT_LEAST_ONE_NONWORD = r"\W+"  # 1 or more non-alphanumeric character
AT_LEAST_ONE_WHITESPACE = r"\s+"  # one or more whitespace chars
AT_LEAST_ONE_NON_NEWLINE_WHITESPACE = r"[ \t]+"  # one or more spaces/tabs

HYPHEN_OR_EN_DASH = r"[-–]"

LEFT_BRACKET = r"\("

NON_ALPHANUMERIC_SPLITTERS = regex.compile(AT_LEAST_ONE_NONWORD, regex.UNICODE)

# http://www.regular-expressions.info/lookaround.html
# Not all engines support lookbehind; e.g. regexr.com doesn't; but Python does
NOT_DIGIT_LOOKBEHIND = r"(?<!\d)"
NOT_DIGIT_LOOKAHEAD = r"(?!\d)"

# The Kleene star has highest precedence.
# So, for example, ab*c matches abbbc, but not (all of) ababc. See regexr.com
OPTIONAL_NONWORD = r"\W*"  # zero or more non-alphanumeric characters...
# ... doesn't need to be [\W]*, for precedence reasons as above.
OPTIONAL_WHITESPACE = r"\s*"  # zero or more whitespace chars
OPTIONAL_NON_NEWLINE_WHITESPACE = r"[ \t]*"  # zero or more spaces/tabs

REGEX_METACHARS = [
    "\\",
    "^",
    "$",
    ".",
    "|",
    "?",
    "*",
    "+",
    "(",
    ")",
    "[",
    "{",
    "#",
    " ",
]
# http://www.regular-expressions.info/characters.html
# Start with \, for replacement.

RIGHT_BRACKET = r"\)"

WB = r"\b"  # word boundary; escape the slash if not using a raw string
WHITESPACE_CHARACTERS = [" ", "\t", "\n"]
WORD_BOUNDARY = WB

_NOT_EMPTY_WORD_ONLY_REGEX = regex.compile(r"^\w+$")
_NOT_EMPTY_ALPHABETICAL_ONLY_REGEX = regex.compile("^[a-zA-Z]+$")
# cf. https://stackoverflow.com/questions/336210/regular-expression-for-alphanumeric-and-underscores  # noqa


# =============================================================================
# Helper functions
# =============================================================================


def escape_literal_string_for_regex(s: str) -> str:
    r"""
    Escape any regex characters. Returns a string.

    For example, maps ``Hello there.`` to ``Hello\ there\.``

    Start with ``\`` -> ``\\``; this should be the first replacement in
    :data:`REGEX_METACHARS`.
    """
    for c in REGEX_METACHARS:
        s = s.replace(c, "\\" + c)
    return s


def escape_literal_for_regex_giving_charlist(s: str) -> List[str]:
    r"""
    Escape any regex characters. Returns a list of characters or escaped
    characters.

    Start with ``\`` -> ``\\``; this should be the first replacement in
    :data:`REGEX_METACHARS`.
    """
    chars = []  # type: List[str]
    for unescaped_char in s:
        if unescaped_char in REGEX_METACHARS:
            chars.append("\\" + unescaped_char)
        else:
            chars.append(unescaped_char)
    return chars


def escape_literal_for_regex_allowing_flexible_whitespace(s: str) -> str:
    r"""
    Escapes literal characters, but creating a regex that allows flexible
    whitespace (e.g. double space) for every bit of whitespace in the original.

    For example, maps ``Hello there.`` to ``Hello\s+there\.``
    """
    # Replace all forms of whitespace with spaces.
    for c in WHITESPACE_CHARACTERS:
        s = s.replace(c, " ")
    # Eliminate double spaces
    while "  " in s:
        s = s.replace("  ", " ")
    # Escape regex characters, except handling whitespace (now, spaces)
    # differently.
    s = escape_literal_string_for_regex(s)
    s = s.replace(r"\ ", AT_LEAST_ONE_WHITESPACE)
    return s


def at_wb_start_end(regex_str: str) -> str:
    """
    Returns a version of the regex starting and ending with a word boundary.

    Caution using this. Digits do not end a word, so "mm3" will not match if
    your "mm" group ends in a word boundary.
    """
    return rf"\b{regex_str}\b"


def at_start_wb(regex_str: str) -> str:
    """
    Returns a version of the regex starting with a word boundary.

    Beware, though; e.g. "3kg" is reasonable, and this does NOT have a word
    boundary in.
    """
    return rf"\b{regex_str}"


def noncapture_group(regex_str: str) -> str:
    """
    Wraps the string in a non-capture group, ``(?: ... )``
    """
    return f"(?:{regex_str})"


def optional_noncapture_group(regex_str: str) -> str:
    """
    Wraps the string in an optional non-capture group, ``(?: ... )?``
    """
    return f"(?:{regex_str})?"


def regex_or(
    *regex_strings: str,
    wrap_each_in_noncapture_group: bool = False,
    wrap_result_in_noncapture_group: bool = False,
) -> str:
    """
    Returns a regex representing an "or" join of the components.

    Args:
        regex_strings:
            The strings to join with ``|``.
        wrap_each_in_noncapture_group:
            Convert each ``component`` into ``(?:component)`` before joining?
        wrap_result_in_noncapture_group:
            Convert the final ``result`` into ``(?:result)``?
    """
    if len(regex_strings) == 1:
        # Add a bit of efficiency.
        only_string = regex_strings[0]
        if wrap_each_in_noncapture_group or wrap_result_in_noncapture_group:
            return noncapture_group(only_string)
        else:
            return only_string
    if wrap_each_in_noncapture_group:
        result = "|".join(noncapture_group(x) for x in regex_strings)
    else:
        result = "|".join(x for x in regex_strings)
    if wrap_result_in_noncapture_group:
        return noncapture_group(result)
    else:
        return result


def assert_alphabetical(x: Union[str, Iterable[str]]) -> None:
    """
    Asserts that the string is not empty and contains only alphabetical
    characters.
    """
    if isinstance(x, str):
        assert _NOT_EMPTY_ALPHABETICAL_ONLY_REGEX.match(x), (
            f"Should be non-empty and contain only alphabetical characters: "
            f"{x!r}"
        )
    else:
        for s in x:
            assert isinstance(s, str)
            assert _NOT_EMPTY_ALPHABETICAL_ONLY_REGEX.match(s), (
                f"Should be non-empty and contain only alphabetical "
                f"characters: {s!r} (part of {x!r})"
            )


def first_n_characters_required(x: str, n: int) -> str:
    """
    Returns a regex string that requires the first n characters, and then
    allows the rest as optional as long as they are in sequence.

    Args:
        x:
            String
        n:
            Minimum number of characters required at the start
    """
    assert _NOT_EMPTY_WORD_ONLY_REGEX.match(x)
    assert n >= 0
    start = x[0:n]
    rest = x[n:]
    rest_regex = ""
    for c in reversed(rest):
        rest_regex = optional_noncapture_group(c + rest_regex)
    return start + rest_regex
