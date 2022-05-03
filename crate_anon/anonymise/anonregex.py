#!/usr/bin/env python

"""
crate_anon/anonymise/anonregex.py

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

**Regular expression functions for anonymisation.**

"""

# =============================================================================
# Imports
# =============================================================================

import calendar
import datetime
import logging
from typing import Iterable, List, Optional, Pattern, Union

from cardinal_pythonlib.lists import unique_list

# https://pypi.python.org/pypi/regex/
# https://bitbucket.org/mrabarnett/mrab-regex
import regex  # sudo apt-get install python-regex

# noinspection PyProtectedMember
from regex import _regex_core

from crate_anon.common.regex_helpers import (
    assert_alphabetical,
    AT_LEAST_ONE_NONWORD,
    escape_literal_for_regex_giving_charlist,
    escape_literal_string_for_regex,
    first_n_characters_required,
    named_capture_group,
    NON_ALPHANUMERIC_SPLITTERS,
    noncapture_group,
    NOT_DIGIT_LOOKAHEAD,
    NOT_DIGIT_LOOKBEHIND,
    OPTIONAL_NON_NEWLINE_WHITESPACE,
    optional_noncapture_group,
    OPTIONAL_NONWORD,
    WORD_BOUNDARY as WB,
)

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

ORDINAL_SUFFIXES_ENGLISH = ("st", "nd", "rd", "th")  # 1st, 2nd, 3rd, 4th...
MONTHS_ENGLISH = tuple(calendar.month_name[_] for _ in range(1, 12 + 1))
# https://docs.python.org/3/library/calendar.html


# =============================================================================
# String manipulation
# =============================================================================


def get_anon_fragments_from_string(s: str) -> List[str]:
    """
    Takes a complex string, such as a name or address with its components
    separated by spaces, commas, etc., and returns a list of substrings to be
    used for anonymisation.

    - For example, from ``"John Smith"``, return ``["John", "Smith"]``;
      from ``"John D'Souza"``, return ``["John", "D", "Souza"]``;
      from ``"42 West Street"``, return ``["42", "West", "Street"]``.

    - Try these examples:

      .. code-block:: python

        get_anon_fragments_from_string("Bob D'Souza")
        get_anon_fragments_from_string("Jemima Al-Khalaim")
        get_anon_fragments_from_string("47 Russell Square")

    - Note that this is a LIBERAL algorithm, i.e. one prone to anonymise too
      much (e.g. all instances of ``"Street"`` if someone has that as part of
      their address).
    - *Note that we use the "word boundary" facility when replacing, and that
      treats apostrophes and hyphens as word boundaries.*
      Therefore, we don't need the largest-level chunks, like ``D'Souza``.
    """
    return list(filter(None, NON_ALPHANUMERIC_SPLITTERS.split(s)))
    # The filter(None, ...) aspect removes empty strings, e.g. from
    # leading/trailing whitespace.


# =============================================================================
# Anonymisation regexes
# =============================================================================

# -----------------------------------------------------------------------------
# Dates
# -----------------------------------------------------------------------------


def _month_word_regex_fragment(month_name: str) -> str:
    """
    Returns possibilities for the month word, allowing the first 3 characters,
    or the whole month name -- e.g. converts ``September`` to
    ``Sep(?:tember)?``, or indeed anything in between 3 and all of the
    characters, e.g. ``Sept``.
    """
    return first_n_characters_required(month_name, 3)


def get_date_regex_elements(
    dt: Union[datetime.datetime, datetime.date],
    at_word_boundaries_only: bool = False,
    ordinal_suffixes: Iterable[str] = ORDINAL_SUFFIXES_ENGLISH,
) -> List[str]:
    """
    Takes a datetime object and returns a list of regex strings with which
    to scrub.

    For example, a date/time of 13 Sep 2014 will produce regexes that recognize
    "13 Sep 2014", "September 13, 2014", "2014/09/13", and many more.

    Args:
        dt:
            The datetime or date or similar object.
        at_word_boundaries_only:
            Ensure that all regexes begin and end with a word boundary
            requirement.
        ordinal_suffixes:
            Language-specific suffixes that may be appended to numbers to make
            them ordinal. In English, "st", "nd", "rd", and "th".

    Returns:
        the list of regular expression strings, as above
    """
    # Day (numeric), allowing leading zeroes and e.g. "1st, 2nd"
    assert_alphabetical(ordinal_suffixes)
    assert not isinstance(ordinal_suffixes, str)
    optional_suffixes = optional_noncapture_group("|".join(ordinal_suffixes))
    day = "0*" + str(dt.day) + optional_suffixes

    # Month
    # ... numerically, allowing leading zeroes for numeric and e.g.
    # Feb/February
    month_numeric = "0*" + str(dt.month)
    # ... as a word
    # month_word = dt.strftime("%B")  # can't cope with years < 1900
    month_name = calendar.month_name[dt.month]  # localized
    # Allow first 3 characters, or whole month name:
    month_word = _month_word_regex_fragment(month_name)
    month = "(?:" + month_numeric + "|" + month_word + ")"

    # Year
    year = str(dt.year)
    if len(year) == 4:
        year = "(?:" + year[0:2] + ")?" + year[2:4]
        # ... converts e.g. 1986 to (19)?86, to match 1986 or 86

    # Separator
    sep = OPTIONAL_NONWORD

    # Regexes
    basic_regexes = [
        day + sep + month + sep + year,  # e.g. 13 Sep 2014
        month + sep + day + sep + year,  # e.g. Sep 13, 2014
        year + sep + month + sep + day,  # e.g. 2014/09/13
    ]
    if at_word_boundaries_only:
        return [WB + x + WB for x in basic_regexes]
    else:
        return basic_regexes


def get_generic_date_regex_elements(
    at_word_boundaries_only: bool = True,
    ordinal_suffixes: Iterable[str] = ORDINAL_SUFFIXES_ENGLISH,
    all_month_names: Iterable[str] = MONTHS_ENGLISH,
) -> List[str]:
    """
    Returns a set of regex elements to scrub *any* date.

    Word boundaries are strongly preferred! This will match some odd things
    otherwise; see the associated unit tests.
    """
    # https://stackoverflow.com/questions/51224/regular-expression-to-match-valid-dates  # noqa

    # range [1, 31]
    numeric_day = named_capture_group(r"0?[1-9]|[12]\d|30|31", "numeric_day")
    # range [1, 12]
    numeric_month = named_capture_group(r"0?[1-9]|1[0-2]", "numeric_month")
    # a 2-digit or 4-digit number
    year = named_capture_group(r"\d{4}|\d{2}", "year")
    sep = r"[^\w\d\r\n:]"  # an active separator
    # ^ = anything not in the set
    # \w = word (alphanumeric and underscore)
    # \d = digit [redundant, I think]
    # \r = carriage return (code 13)
    # \n = linefeed (code 10)
    # : = colon

    # For ordinal days:
    day = numeric_day + optional_noncapture_group("|".join(ordinal_suffixes))

    # To be able to capture ISO dates like "20010101", but not capture e.g.
    # "31/12" as 3, 1, 12, we require separators normally and do a special for
    # ISO dates:
    two_digit_day = noncapture_group(r"0[1-9]|[12]\d|30|31")
    two_digit_month = noncapture_group(r"0[1-9]|1[0-2]")
    isodate_no_sep = year + two_digit_month + two_digit_day
    # Then for months as words:
    month = named_capture_group(
        "|".join(
            [numeric_month]
            + [_month_word_regex_fragment(m) for m in all_month_names]
        ),
        "month",
    )

    basic_regexes = [
        f"(?P<day_month_year>{day}{sep}{month}{sep}{year})",  # e.g. UK
        f"(?P<month_day_year>{month}{sep}{day}{sep}{year})",  # e.g. USA
        f"(?P<year_month_day>{year}{sep}{month}{sep}{day})",  # e.g. ISO
        f"(?P<isodate_no_sep>{isodate_no_sep})",  # ISO with no separators
    ]
    if at_word_boundaries_only:
        return [WB + x + WB for x in basic_regexes]
    else:
        # Even if we don't require a strict word boundary, we can't allow just
        # anything -- you get garbage if numbers precede numeric dates.
        non_numeric_boundary = noncapture_group(r"\b|[\WA-Za-z_]")
        # \b word boundary = change from word to non-word (or the reverse)
        # \w = word = alphanumeric and underscore
        # ... so we take the subset that is alphabetical and underscore
        # \W = nonword = everything not in \w
        return [
            non_numeric_boundary + x + non_numeric_boundary
            for x in basic_regexes
        ]


# -----------------------------------------------------------------------------
# Generic codes
# -----------------------------------------------------------------------------


def get_code_regex_elements(
    s: str,
    liberal: bool = True,
    very_liberal: bool = True,
    at_word_boundaries_only: bool = True,
    at_numeric_boundaries_only: bool = True,
) -> List[str]:
    """
    Takes a **string** representation of a number or an alphanumeric code,
    which may include leading zeros (as for phone numbers), and produces a list
    of regex strings for scrubbing.

    We allow all sorts of separators. For example, 0123456789 might appear as

    .. code-block:: none

        (01234) 56789
        0123 456 789
        01234-56789
        0123.456.789

    This can also be used for postcodes, which should have whitespace
    prestripped, so e.g. PE123AB might appear as

    .. code-block:: none

        PE123AB
        PE12 3AB
        PE 12 3 AB

    Args:
        s:
            The string representation of a number or code.
        liberal:
            Boolean. Use "optional non-newline whitespace" to separate
            characters in the source.
        very_liberal:
            Boolean. Use "optional nonword" to separate characters in the
            source.
        at_word_boundaries_only:
            Boolean. Ensure that the regex begins and ends with a word boundary
            requirement. So, if True, "123" will not be scrubbed from "M123".
        at_numeric_boundaries_only:
            Boolean. Only applicable if ``at_numeric_boundaries_only`` is
            False. Ensure that the number/code is only recognized when
            surrounded by non-numbers; that is, only at the boundaries of
            numbers (at numeric boundaries).

            - Applicable if ``not at_word_boundaries_only``.

            - Even though we're not restricting to word boundaries, because
              (for example) we want ``123456`` to match ``M123456``, it can be
              undesirable to match numbers that are bordered only by numbers;
              that is, with this setting, ``23`` should never match ``234`` or
              ``1234`` or ``123``.

            - If set, this option ensures that the number/code is recognized
              only when it is bordered by non-numbers.

            - But if you want to anonymise "123456" out of a phone number
              written like "01223123456", you might have to turn this off...

    Returns:
        a list of regular expression strings

    """
    if not s:
        return []
    chars = escape_literal_for_regex_giving_charlist(
        s
    )  # escape any decimal points, etc.  # noqa
    if very_liberal:
        separators = OPTIONAL_NONWORD
    elif liberal:
        separators = OPTIONAL_NON_NEWLINE_WHITESPACE
    else:
        separators = ""
    s = separators.join([c for c in chars])  # ... can appear anywhere
    if at_word_boundaries_only:
        return [WB + s + WB]
    else:
        if at_numeric_boundaries_only:
            # http://www.regular-expressions.info/lookaround.html
            # https://stackoverflow.com/questions/15099150/regex-find-one-digit-number  # noqa
            return [NOT_DIGIT_LOOKBEHIND + s + NOT_DIGIT_LOOKAHEAD]
        else:
            return [s]


# -----------------------------------------------------------------------------
# Generic numbers
# -----------------------------------------------------------------------------


def get_number_of_length_n_regex_elements(
    n: int,
    liberal: bool = True,
    very_liberal: bool = False,
    at_word_boundaries_only: bool = True,
) -> List[str]:
    """
    Get a list of regex strings for scrubbing n-digit numbers -- for
    example, to remove all 10-digit numbers as putative NHS numbers, or all
    11-digit numbers as putative UK phone numbers.

    Args:
        n: the length of the number
        liberal:
            Boolean. Use "optional non-newline whitespace" to separate
            the digits.
        very_liberal:
            Boolean. Use "optional nonword" to separate the digits.
        at_word_boundaries_only:
            Boolean. If set, ensure that the regex begins and ends with a word
            boundary requirement. If not set, the regex must be surrounded by
            non-digits. (If it were surrounded by more digits, it wouldn't be
            an n-digit number!)

    Returns:
        a list of regular expression strings

    """
    s = ["[0-9]"] * n
    if very_liberal:
        separators = OPTIONAL_NONWORD
    elif liberal:
        separators = OPTIONAL_NON_NEWLINE_WHITESPACE
    else:
        separators = ""
    s = separators.join([c for c in s])
    if at_word_boundaries_only:
        return [WB + s + WB]
    else:
        return [NOT_DIGIT_LOOKBEHIND + s + NOT_DIGIT_LOOKAHEAD]
        # ... if there was a digit before/after, it's not an n-digit number


# -----------------------------------------------------------------------------
# UK postcodes
# -----------------------------------------------------------------------------


def get_uk_postcode_regex_elements(
    at_word_boundaries_only: bool = True,
) -> List[str]:
    """
    Get a list of regex strings for scrubbing UK postcodes. These have a
    well-defined format.

    Unless compiled with the ``re.IGNORECASE``, they will match upper-case
    postcodes only.

    Args:
        at_word_boundaries_only:
            Boolean. If set, ensure that the regex begins and ends with a word
            boundary requirement.

    Returns:
        a list of regular expression strings

    See:

    - https://stackoverflow.com/questions/164979/regex-for-matching-uk-postcodes
    """  # noqa
    # -------------------------------------------------------------------------
    # Old
    # -------------------------------------------------------------------------

    # e = [
    #     "AN NAA",
    #     "ANN NAA",
    #     "AAN NAA",
    #     "AANN NAA",
    #     "ANA NAA",
    #     "AANA NAA",
    # ]  # type: List[str]
    # for i in range(len(e)):
    #     e[i] = e[i].replace("A", "[A-Z]")  # letter
    #     e[i] = e[i].replace("N", "[0-9]")  # number
    #     e[i] = e[i].replace(" ", OPTIONAL_WHITESPACE)
    #     if at_word_boundaries_only:
    #         e[i] = WB + e[i] + WB
    # return e

    # -------------------------------------------------------------------------
    # New 2020-04-28: much more efficient
    # -------------------------------------------------------------------------
    e = r"[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}"
    if at_word_boundaries_only:
        e = WB + e + WB
    return [e]


def get_uk_postcode_regex_string(at_word_boundaries_only: bool = True) -> str:
    """
    Shortcut to retrieve a single regex string for UK postcodes (following the
    changes above on 2020-04-28). See :func:`get_uk_postcode_regex_elements`.
    """
    postcode_regexes = get_uk_postcode_regex_elements(
        at_word_boundaries_only=at_word_boundaries_only
    )
    assert len(postcode_regexes) == 1  # as of 2020-04-28, this is true
    return postcode_regexes[0]


# -----------------------------------------------------------------------------
# Generic strings and phrases
# -----------------------------------------------------------------------------
# Note, for strings, several typo-detecting methods:
#   http://en.wikipedia.org/wiki/Levenshtein_distance
#   http://mwh.geek.nz/2009/04/26/python-damerau-levenshtein-distance/
#   http://en.wikipedia.org/wiki/TRE_(computing)
#   https://pypi.python.org/pypi/regex
# ... let's go with the fuzzy regex method (Python regex module).


def get_string_regex_elements(
    s: str,
    suffixes: List[str] = None,
    at_word_boundaries_only: bool = True,
    max_errors: int = 0,
) -> List[str]:
    """
    Takes a string and returns a list of regex strings with which to scrub.

    Args:
        s:
            The starting string.
        suffixes:
            A list of suffixes to permit, typically ``["s"]``.
        at_word_boundaries_only:
            Boolean. If set, ensure that the regex begins and ends with a word
            boundary requirement.
            (If false: will scrub ``ANN`` from ``bANNed``.)
        max_errors:
            The maximum number of typographical insertion/deletion/substitution
            errors to permit.

    Returns:
        a list of regular expression strings

    """
    if not s:
        return []
    s = escape_literal_string_for_regex(s)
    if max_errors > 0:
        s = "(" + s + "){e<" + str(max_errors + 1) + "}"
        # - a leading (?e) forces a search for a better match than the first;
        #   the other way is to specify the regex.ENHANCEMATCH flag...
        #   however, when doing this in get_regex_from_elements(), we got a
        #   segmentation fault... and, less consistently, when we put it here.
        #   So skip that!
        # - (...) is the pattern
        # - suffix up to n insertion/deletion/substitution errors
        # ... https://pypi.python.org/pypi/regex
        # ... http://www.gossamer-threads.com/lists/python/python/1002881
    if suffixes:
        suffixstr = (
            "(?:"
            + "|".join([escape_literal_string_for_regex(x) for x in suffixes])
            + "|)"  # allows for no suffix at all
        )
    else:
        suffixstr = ""
    if at_word_boundaries_only:
        return [WB + s + suffixstr + WB]
    else:
        return [s + suffixstr]


def get_phrase_regex_elements(
    phrase: str,
    suffixes: List[str] = None,
    at_word_boundaries_only: bool = True,
    max_errors: int = 0,
    alternatives: List[List[str]] = None,
) -> List[str]:
    """
    Gets regular expressions to scrub a phrase; that is, all words within a
    phrase consecutively.

    Args:
        phrase:
            E.g. '4 Privet Drive'.
        suffixes:
            A list of suffixes to permit (unusual).
        at_word_boundaries_only:
            Apply regex only at word boundaries?
        max_errors:
            Maximum number of typos, as defined by the regex module.
        alternatives:
            This allows words to be substituted by equivalents; such as
            ``St`` for ``Street`` or ``Rd`` for ``Road``. The parameter is a
            list of lists of equivalents; see
            :func:`crate_anon.anonymise.config.get_word_alternatives`.

    Returns:
        A list of regex fragments.
    """

    # Break the phrase into consecutive strings.
    strings = get_anon_fragments_from_string(phrase)
    if not strings:
        return []

    if alternatives:
        # If we're allowing alternatives...
        for i, string in enumerate(strings):
            upperstring = string.upper()
            found_equivalents = False
            for equivalent_words in alternatives:
                if upperstring in equivalent_words:
                    # Found it. Replace our single word with a regex
                    # representing a whole set of alternatives (including what
                    # we started with).
                    strings[i] = (
                        "(?:"
                        + "|".join(
                            escape_literal_string_for_regex(x)
                            for x in equivalent_words
                        )
                        + ")"
                    )
                    found_equivalents = True
                    break
            if not found_equivalents:
                # No equivalents; just escape what we have
                strings[i] = escape_literal_string_for_regex(string)
    else:
        # Otherwise, escape what we have
        strings = [escape_literal_string_for_regex(x) for x in strings]

    s = AT_LEAST_ONE_NONWORD.join(strings)
    if max_errors > 0:
        s = "(" + s + "){e<" + str(max_errors + 1) + "}"
    if suffixes:
        suffixstr = (
            "(?:"
            + "|".join([escape_literal_string_for_regex(x) for x in suffixes])
            + "|)"  # allows for no suffix at all
        )
    else:
        suffixstr = ""
    if at_word_boundaries_only:
        return [WB + s + suffixstr + WB]
    else:
        return [s + suffixstr]


# =============================================================================
# Combining regex elements into a giant regex
# =============================================================================


def get_regex_string_from_elements(elementlist: List[str]) -> str:
    """
    Convert a list of regex elements into a single regex string.
    """
    if not elementlist:
        return ""
    return "|".join(unique_list(elementlist))
    # The or operator | has the lowest precedence.
    # ... http://www.regular-expressions.info/alternation.html
    # We also want to minimize the number of brackets.
    # THEREFORE, ANYTHING CONTRIBUTING FRAGMENTS HERE SHOULD NOT HAVE |
    # OPERATORS AT ITS TOP LEVEL. If it does, it should encapsulate them in a
    # non-capturing group, (?:...)


def get_regex_from_elements(elementlist: List[str]) -> Optional[Pattern]:
    """
    Convert a list of regex elements into a compiled regex, which will operate
    in case-insensitive fashion on Unicode strings.
    """
    if not elementlist:
        return None
    try:
        s = get_regex_string_from_elements(elementlist)
        return regex.compile(
            s,
            regex.IGNORECASE | regex.UNICODE | regex.VERBOSE | regex.MULTILINE,
        )
    except _regex_core.error:
        log.exception(f"Failed regex: elementlist={elementlist}")
        raise
