"""
crate_anon/nlp_manager/regex_func.py

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

**Functions to assist in building regular expressions.**

2019-01-01: RM notes Ragel (https://en.wikipedia.org/wiki/Ragel) for embedding
actions within a regex parser. Not immediately applicable here, I don't think,
but bear in mind.

"""

import logging
from typing import Any, Dict, Optional, Pattern, Tuple

import regex

# noinspection PyProtectedMember
from regex import _regex_core

log = logging.getLogger(__name__)


# =============================================================================
# Core regex functions
# =============================================================================
# - All will use VERBOSE mode for legibility. (No impact on speed: compiled.)
# - Don't forget to use raw strings for all regex definitions!
# - Beware comments inside regexes. The comment parser isn't quite as benign
#   as you might think. Use very plain text only.
# - (?: XXX ) makes XXX into an unnamed group.


REGEX_COMPILE_FLAGS = (
    regex.IGNORECASE | regex.MULTILINE | regex.VERBOSE | regex.UNICODE
)


def compile_regex(regex_str: str) -> Pattern:
    """
    Compiles a regular expression with our standard flags.
    """
    try:
        return regex.compile(regex_str, REGEX_COMPILE_FLAGS)
    except _regex_core.error:
        log.critical(f"FAILING REGEX:\n{regex_str}")
        raise


def compile_regex_dict(
    regexstr_to_value_dict: Dict[str, Any]
) -> Dict[Pattern, Any]:
    """
    Converts a dictionary ``{regex_str: value}`` to a dictionary
    ``{compiled_regex: value}``.
    """
    return {compile_regex(k): v for k, v in regexstr_to_value_dict.items()}


def get_regex_dict_match(
    text: Optional[str],
    regex_to_value_dict: Dict[Pattern, Any],
    default: Any = None,
) -> Tuple[bool, Any]:
    """
    Checks text against a set of regular expressions. Returns whether there is
    a match, and if there was a match, the value that was associated (in the
    dictionary) with the matching regex.

    (Note: "match", as usual, means "match at the beginning of the string".)

    Args:
        text:
            text to test
        regex_to_value_dict:
            dictionary mapping ``{compiled_regex: value}``
        default:
            value to return if there is no match

    Returns:
        tuple: ``matched, associated_value_or_default``

    """
    if text:
        for r, value in regex_to_value_dict.items():
            if r.match(text):
                return True, value
    return False, default


def get_regex_dict_search(
    text: Optional[str],
    regex_to_value_dict: Dict[Pattern, Any],
    default: Any = None,
) -> Tuple[bool, Any]:
    """
    As for :func:`get_regex_dict_match`, but performs a search (find anywhere
    in the string) rather than a match.
    """
    if text:
        for r, value in regex_to_value_dict.items():
            if r.search(text):
                return True, value
    return False, default
