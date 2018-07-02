#!/usr/bin/env python
# crate_anon/anonymise/anonregex.py

"""
===============================================================================

    Copyright (C) 2015-2018 Rudolf Cardinal (rudolf@pobox.com).

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

# =============================================================================
# Imports
# =============================================================================

import calendar
import datetime
import dateutil.parser  # for unit tests
import logging
from typing import List, Optional, Pattern, Union
import unittest

from cardinal_pythonlib.lists import unique_list
from cardinal_pythonlib.logs import configure_logger_for_colour

# https://pypi.python.org/pypi/regex/
# https://bitbucket.org/mrabarnett/mrab-regex
import regex  # sudo apt-get install python-regex
# noinspection PyProtectedMember
from regex import _regex_core

from crate_anon.common.stringfunc import (
    get_digit_string_from_vaguely_numeric_string,  # for unit testing
    reduce_to_alphanumeric,  # for unit testing
)

log = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

REGEX_METACHARS = ["\\", "^", "$", ".",
                   "|", "?", "*", "+",
                   "(", ")", "[", "{"]
# http://www.regular-expressions.info/characters.html
# Start with \, for replacement.

WB = r"\b"  # word boundary; escape the slash if not using a raw string

# http://www.regular-expressions.info/lookaround.html
# Not all engines support lookbehind; e.g. regexr.com doesn't; but Python does
NOT_DIGIT_LOOKBEHIND = r"(?<!\d)"
NOT_DIGIT_LOOKAHEAD = r"(?!\d)"

# The Kleene star has highest precedence.
# So, for example, ab*c matches abbbc, but not (all of) ababc. See regexr.com
OPTIONAL_NONWORD = r"\W*"  # zero or more non-alphanumeric characters...
# ... doesn't need to be [\W]*, for precedence reasons as above.
AT_LEAST_ONE_NONWORD = r"\W+"  # 1 or more non-alphanumeric character

NON_ALPHANUMERIC_SPLITTERS = regex.compile(AT_LEAST_ONE_NONWORD, regex.UNICODE)

OPTIONAL_WHITESPACE = r"\s*"  # zero or more whitespace chars
OPTIONAL_NON_NEWLINE_WHITESPACE = r"[ \t]*"  # zero or more spaces/tabs


# =============================================================================
# String manipulation
# =============================================================================

def get_anon_fragments_from_string(s: str) -> List[str]:
    """
    Takes a complex string, such as a name or address with its components
    separated by spaces, commas, etc., and returns a list of substrings to be
    used for anonymisation.
    - For example, from "John Smith", return ["John", "Smith"];
      from "John D'Souza", return ["John", "D", "Souza"];
      from "42 West Street", return ["42", "West", "Street"].

    - Try the examples listed below the function.
    - Note that this is a LIBERAL algorithm, i.e. one prone to anonymise too
      much (e.g. all instances of "Street" if someone has that as part of their
      address).
    - NOTE THAT WE USE THE "WORD BOUNDARY" FACILITY WHEN REPLACING, AND THAT
      TREATS APOSTROPHES AND HYPHENS AS WORD BOUNDARIES.
      Therefore, we don't need the largest-level chunks, like D'Souza.
    """
    return NON_ALPHANUMERIC_SPLITTERS.split(s)
    # smallfragments = []
    # combinedsmallfragments = []
    # for chunk in s.split():  # split on whitespace
    #     for smallchunk in NON_WHITESPACE_SPLITTERS.split(chunk):
    #         if smallchunk.lower() in config.words_not_to_scrub:
    #             continue
    #         smallfragments.append(smallchunk)
    #         # OVERLAP here, but we need it for the combination bit, and
    #         # we remove the overlap at the end.
    # # Now we have chunks with e.g. apostrophes in, and all chunks split by
    # # everything. Finally, we want all of these lumped together.
    # for L in xrange(len(smallfragments) + 1):
    #     for subset in itertools.combinations(smallfragments, L):
    #         if subset:
    #             combinedsmallfragments.append("".join(subset))
    # return list(set(smallfragments + combinedsmallfragments))
# EXAMPLES:
# get_anon_fragments_from_string("Bob D'Souza")
# get_anon_fragments_from_string("Jemima Al-Khalaim")
# get_anon_fragments_from_string("47 Russell Square")


# =============================================================================
# Regexes
# =============================================================================

def escape_literal_string_for_regex(s: str) -> str:
    r"""
    Escape any regex characters.

    Start with \ -> \\
        ... this should be the first replacement in REGEX_METACHARS.
    """
    for c in REGEX_METACHARS:
        s.replace(c, "\\" + c)
    return s


# =============================================================================
# Anonymisation regexes
# =============================================================================
# Note, for strings, several typo-detecting methods:
#   http://en.wikipedia.org/wiki/Levenshtein_distance
#   http://mwh.geek.nz/2009/04/26/python-damerau-levenshtein-distance/
#   http://en.wikipedia.org/wiki/TRE_(computing)
#   https://pypi.python.org/pypi/regex
# ... let's go with the fuzzy regex method (Python regex module).

def get_date_regex_elements(
        dt: Union[datetime.datetime, datetime.date],
        at_word_boundaries_only: bool = False) -> List[str]:
    """
    Takes a datetime object and returns a list of regex strings with which
    to scrub.
    """
    # Reminders: ? zero or one, + one or more, * zero or more
    # Non-capturing groups: (?:...)
    # ... https://docs.python.org/2/howto/regex.html
    # ... http://stackoverflow.com/questions/3512471/non-capturing-group
    # Day, allowing leading zeroes and e.g. "1st, 2nd"
    day = "0*" + str(dt.day) + "(?:st|nd|rd|th)?"
    # Month, allowing leading zeroes for numeric and e.g. Feb/February
    month_numeric = "0*" + str(dt.month)
    # month_word = dt.strftime("%B")  # can't cope with years < 1900
    month_word = calendar.month_name[dt.month]
    month_word = month_word[0:3] + "(?:" + month_word[3:] + ")?"
    month = "(?:" + month_numeric + "|" + month_word + ")"
    # Year
    year = str(dt.year)
    if len(year) == 4:
        year = "(?:" + year[0:2] + ")?" + year[2:4]
        # ... converts e.g. 1986 to (19)?86, to match 1986 or 86
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


def get_code_regex_elements(
        s: str,
        liberal: bool = True,
        very_liberal: bool = True,
        at_word_boundaries_only: bool = True,
        at_numeric_boundaries_only: bool = False) -> List[str]:
    """
    Takes a STRING representation of a number or an alphanumeric code, which
    may include leading zeros (as for phone numbers), and produces a list of
    regex strings for scrubbing.

    We allow all sorts of separators. For example, 0123456789 might appear as
        (01234) 56789
        0123 456 789
        01234-56789
        0123.456.789

    This can also be used for postcodes, which should have whitespace
    prestripped, so e.g. PE123AB might appear as
        PE123AB
        PE12 3AB
        PE 12 3 AB
    """
    if not s:
        return []
    s = escape_literal_string_for_regex(s)  # escape any decimal points, etc.
    if very_liberal:
        separators = OPTIONAL_NONWORD
    elif liberal:
        separators = OPTIONAL_NON_NEWLINE_WHITESPACE
    else:
        separators = ""
    s = separators.join([c for c in s])  # ... can appear anywhere
    if at_word_boundaries_only:
        return [WB + s + WB]
    else:
        if at_numeric_boundaries_only:
            # Even though we're not restricting to word boundaries, because
            # (for example) we want 123456 to match "M123456", it can be
            # undesirable match numbers that are bordered only by numbers; that
            # is, with this setting, "23" should never match "234" or "1234"
            # or "123".
            # - http://www.regular-expressions.info/lookaround.html
            # - http://stackoverflow.com/questions/15099150/regex-find-one-digit-number  # noqa
            return [NOT_DIGIT_LOOKBEHIND + s + NOT_DIGIT_LOOKAHEAD]
        else:
            # But if you want to anonymise "123456" out of a phone number
            # written like "01223123456", you might have to turn that off...
            return [s]


def get_number_of_length_n_regex_elements(
        n: int,
        liberal: bool = True,
        very_liberal: bool = False,
        at_word_boundaries_only: bool = True) -> List[str]:
    """
    Get a list of regex strings for scrubbing n-digit numbers -- for
    example, to remove all 10-digit numbers as putative NHS numbers, or all
    11-digit numbers as putative UK phone numbers.
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


def get_uk_postcode_regex_elements(
        at_word_boundaries_only: bool = True) -> List[str]:
    """
    Get a list of regex strings for scrubbing UK postcodes.
    """
    e = [
        "AN NAA",
        "ANN NAA",
        "AAN NAA",
        "AANN NAA",
        "ANA NAA",
        "AANA NAA",
    ]
    for i in range(len(e)):
        e[i] = e[i].replace("A", "[A-Z]")  # letter
        e[i] = e[i].replace("N", "[0-9]")  # number
        e[i] = e[i].replace(" ", OPTIONAL_WHITESPACE)
        if at_word_boundaries_only:
            e[i] = WB + e[i] + WB
    return e


def get_string_regex_elements(
        s: str,
        suffixes: List[str] = None,
        at_word_boundaries_only: bool = True,
        max_errors: int = 0) -> List[str]:
    """
    Takes a string and returns a list of regex strings with which to scrub.
    Options:
    - list of suffixes to permit, typically ["s"]
    - typographical errors
    - whether to constrain to word boundaries or not
        ... if false: will scrub ANN from bANNed
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
            "(?:" +
            "|".join([escape_literal_string_for_regex(x) for x in suffixes]) +
            "|)"  # allows for no suffix at all
        )
    else:
        suffixstr = ""
    if at_word_boundaries_only:
        return [WB + s + suffixstr + WB]
    else:
        return [s + suffixstr]


def get_phrase_regex_elements(
        phrase: str,
        at_word_boundaries_only: bool = True,
        max_errors: int = 0,
        alternatives: List[List[str]] = None) -> List[str]:
    """
    Args:
        phrase: e.g. '4 Privet Drive'
        at_word_boundaries_only: apply regex only at word boundaries
        max_errors: maximum number of typos, as defined by the regex module
        alternatives: list of lists of equivalents; see get_word_alternatives()

    Returns:
        A list of regex fragments.
    """
    strings = get_anon_fragments_from_string(phrase)
    if not strings:
        return []
    strings = [escape_literal_string_for_regex(x) for x in strings]
    if alternatives:
        for i, string in enumerate(strings):
            upperstring = string.upper()
            found_equivalents = False
            for equivalent_words in alternatives:
                if upperstring in equivalent_words:
                    strings[i] = (
                        "(?:" +
                        "|".join(escape_literal_string_for_regex(x)
                                 for x in equivalent_words)
                        + ")"
                    )
                    found_equivalents = True
                    break
            if not found_equivalents:
                strings[i] = escape_literal_string_for_regex(string)
    else:
        strings = [escape_literal_string_for_regex(x) for x in strings]
    s = AT_LEAST_ONE_NONWORD.join(strings)
    if max_errors > 0:
        s = "(" + s + "){e<" + str(max_errors + 1) + "}"
    if at_word_boundaries_only:
        return [WB + s + WB]
    else:
        return [s]


# =============================================================================
# Combining regex elements into a giant regex
# =============================================================================

def get_regex_string_from_elements(elementlist: List[str]) -> str:
    """
    Convert a list of regex elements into a single regex string.
    """
    if not elementlist:
        return ""
    return u"|".join(unique_list(elementlist))
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
        return regex.compile(s, regex.IGNORECASE | regex.UNICODE)
    except _regex_core.error:
        log.exception("Failed regex: elementlist={}".format(elementlist))
        raise


# =============================================================================
# Unit tests
# =============================================================================

class TestAnonRegexes(unittest.TestCase):
    STRING_1 = r"""
        I was born on 07 Jan 2013, m'lud.
        It was 7 January 13, or 7/1/13, or 1/7/13, or
        Jan 7 2013, or 2013/01/07, or 2013-01-07,
        or 7th January
        13 (split over a line)
        or Jan 7th 13
        or 07.01.13 or 7.1.2013
        or a host of other variations.
        And ISO-8601 formats like 20130107T0123, or just 20130107.

        BUT NOT 8 Jan 2013, or 2013/02/07, or 2013
        Jan 17, or just a number like 7, or a month
        like January, or a nonspecific date like
        Jan 2013 or 7 January. And not ISO-8601-formatted other dates
        like 20130108T0123, or just 20130108.

        I am 34 years old. My mother was 348, or 834, or perhaps 8348.
        Was she 34.6? Don't think so.

        Her IDs include NHS#123456, or 123 456, or (123) 456, or 123456.

        I am 34 years old. My mother was 348, or 834, or perhaps 8348.
        She wasn't my step-mother, or my grandmother, or my mother-in-law.
        She was my MOTHER!
        A typo is mther.

        Unicode apostrophe: the thread’s possession

        E-mail: bob@pobox.com, mr.jones@somewhere.nhs.uk, blah@place.com
        Mr.Jones@somewhere.nhs.uk

        Some numbers by size:
            1
            12
            123
            1234
            12345
            123456
            1234567
            12345678
            123456789
            1234567890
            12345678901
            123456789012
            1234567890123
            12345678901234
            123456789012345
        Some postcodes (from https://www.mrs.org.uk/pdf/postcodeformat.pdf)
            M1 1AA
            M60 1NW
            CR2 6XH
            DN55 1PT
            W1A 1HQ
            EC1A 1BB
    """

    @staticmethod
    def report(title: str, string: str) -> None:
        print("=" * 79)
        print(title)
        print("=" * 79)
        print(string)

    def test_most(self) -> None:
        s = self.STRING_1
        testnumber = 34
        testnumber_as_text = "123456"
        testdate_str = "7 Jan 2013"
        testdate = dateutil.parser.parse(testdate_str)
        teststring = "mother"
        testphrase = "348 or 834"
        date_19th_c = "3 Sep 1847"
        old_testdate = dateutil.parser.parse(date_19th_c)
        testemail = "mr.jones@somewhere.nhs.uk"

        regex_date = get_regex_from_elements(get_date_regex_elements(testdate))
        regex_number = get_regex_from_elements(
            get_code_regex_elements(str(testnumber)))
        regex_number_as_text = get_regex_from_elements(
            get_code_regex_elements(
                get_digit_string_from_vaguely_numeric_string(
                    testnumber_as_text)))
        regex_string = get_regex_from_elements(
            get_string_regex_elements(teststring))
        regex_email = get_regex_from_elements(
            get_string_regex_elements(testemail))
        regex_phrase = get_regex_from_elements(
            get_phrase_regex_elements(testphrase))
        regex_10digit = get_regex_from_elements(
            get_number_of_length_n_regex_elements(10))
        regex_postcode = get_regex_from_elements(
            get_uk_postcode_regex_elements())
        all_elements = (
            get_date_regex_elements(testdate) +
            get_code_regex_elements(str(testnumber)) +
            get_code_regex_elements(
                get_digit_string_from_vaguely_numeric_string(
                    testnumber_as_text)) +
            get_string_regex_elements(teststring) +
            get_string_regex_elements(testemail) +
            get_phrase_regex_elements(testphrase) +
            get_number_of_length_n_regex_elements(10) +
            get_uk_postcode_regex_elements()
        )
        regex_all = get_regex_from_elements(all_elements)

        self.report("Removing date: " + testdate_str,
                    regex_date.sub("DATE_GONE", s))
        self.report("Removing number: {}".format(testnumber),
                    regex_number.sub("NUMBER_GONE", s))
        self.report("Removing numbers as text: " + testnumber_as_text,
                    regex_number_as_text.sub("NUMBER_AS_TEXT_GONE", s))
        self.report("Removing string: " + teststring,
                    regex_string.sub("STRING_GONE", s))
        self.report("Removing email: " + testemail,
                    regex_email.sub("EMAIL_GONE", s))
        self.report("Removing phrase: " + testphrase,
                    regex_phrase.sub("PHRASE_GONE", s))
        self.report("Removing 10-digit numbers",
                    regex_10digit.sub("TEN_DIGIT_NUMBERS_GONE", s))
        self.report("Removing postcodes",
                    regex_postcode.sub("POSTCODES_GONE", s))
        self.report("Removing everything", regex_all.sub("EVERYTHING_GONE", s))
        self.report("All-elements regex",
                    get_regex_string_from_elements(all_elements))
        self.report("Date regex",
                    get_regex_string_from_elements(
                        get_date_regex_elements(testdate)))
        self.report("Date regex for 19th century",
                    get_regex_string_from_elements(
                        get_date_regex_elements(old_testdate)))
        self.report("Phrase regex", get_regex_string_from_elements(
            get_phrase_regex_elements(testphrase)))
        self.report("10-digit-number regex", get_regex_string_from_elements(
            get_number_of_length_n_regex_elements(10)))


def examples_for_paper():
    testwords = "John Al'Rahem"
    min_string_length_to_scrub_with = 4
    scrub_string_suffixes = []  # type: List[str]
    max_errors = 0
    at_word_boundaries_only = True
    words_regexes = []  # type: List[str]
    for s in get_anon_fragments_from_string(testwords):
        length = len(s)
        if length < min_string_length_to_scrub_with:
            continue
        words_regexes.extend(get_string_regex_elements(
            s,
            suffixes=scrub_string_suffixes,
            at_word_boundaries_only=at_word_boundaries_only,
            max_errors=max_errors
        ))
    print("--- For words {}:".format(testwords))
    for r in words_regexes:
        print(r)

    testphrase = "4 Privet Drive"
    phrase_regexes = get_phrase_regex_elements(
        testphrase,
        max_errors=max_errors,
        at_word_boundaries_only=at_word_boundaries_only
    )
    print("--- For phrase {}:".format(testphrase))
    for r in phrase_regexes:
        print(r)

    testnumber = "(01223) 123456"
    anonymise_numbers_at_word_boundaries_only = False
    anonymise_numbers_at_numeric_boundaries_only = True
    number_regexes = get_code_regex_elements(
        get_digit_string_from_vaguely_numeric_string(str(testnumber)),
        at_word_boundaries_only=anonymise_numbers_at_word_boundaries_only,
        at_numeric_boundaries_only=anonymise_numbers_at_numeric_boundaries_only
    )
    print("--- For number {}:".format(testnumber))
    for r in number_regexes:
        print(r)

    testcode = "CB12 3DE"
    anonymise_codes_at_word_boundaries_only = True
    code_regexes = get_code_regex_elements(
        reduce_to_alphanumeric(str(testcode)),
        at_word_boundaries_only=anonymise_codes_at_word_boundaries_only
    )
    print("--- For code {}:".format(testcode))
    for r in code_regexes:
        print(r)

    n_digits = 10
    nonspec_10_digit_number_regexes = get_number_of_length_n_regex_elements(
        n_digits,
        at_word_boundaries_only=anonymise_numbers_at_word_boundaries_only
    )
    print("--- NONSPECIFIC: numbers of length {}:".format(n_digits))
    for r in nonspec_10_digit_number_regexes:
        print(r)

    uk_postcode_regexes = get_uk_postcode_regex_elements(
        at_word_boundaries_only=anonymise_codes_at_word_boundaries_only
    )
    print("--- NONSPECIFIC: UK postcodes:")
    for r in uk_postcode_regexes:
        print(r)

    testdate = datetime.date(year=2016, month=12, day=31)
    date_regexes = get_date_regex_elements(testdate)
    print("--- For date {}:".format(testdate))
    for r in date_regexes:
        print(r)


if __name__ == '__main__':
    rootlogger = logging.getLogger()
    configure_logger_for_colour(rootlogger, level=logging.DEBUG)
    # unittest.main()
    examples_for_paper()
