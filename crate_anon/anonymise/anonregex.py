#!/usr/bin/env python3
# crate_anon/anonymise/anonregex.py

"""
Core anonymisation functions for CRATE.

Author: Rudolf Cardinal
Created at: 18 Feb 2015
Last update: 24 Nov 2015

Copyright/licensing:

    Copyright (C) 2015-2016 Rudolf Cardinal (rudolf@pobox.com).
    Department of Psychiatry, University of Cambridge.

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

"""

# =============================================================================
# Imports
# =============================================================================

import calendar
import logging
import regex  # sudo apt-get install python-regex

log = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

NON_ALPHANUMERIC_SPLITTERS = regex.compile("[\W]+", regex.UNICODE)
# 1 or more non-alphanumeric characters...

REGEX_METACHARS = ["\\", "^", "$", ".",
                   "|", "?", "*", "+",
                   "(", ")", "[", "{"]
# http://www.regular-expressions.info/characters.html
# Start with \, for replacement.

WB = r"\b"  # word boundary; escape the slash if not using a raw string


# =============================================================================
# String manipulation
# =============================================================================

def get_digit_string_from_vaguely_numeric_string(s):
    """
    Strips non-digit characters from a string.
    For example, converts "(01223) 123456" to "01223123456".
    """
    return "".join([d for d in s if d.isdigit()])


def reduce_to_alphanumeric(s):
    """
    Strips non-alphanumeric characters from a string.
    For example, converts "PE12 3AB" to "PE12 3AB".
    """
    return "".join([d for d in s if d.isalnum()])


def remove_whitespace(s):
    """
    Removes whitespace from a string.
    """
    return ''.join(s.split())


def get_anon_fragments_from_string(s):
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

def escape_literal_string_for_regex(s):
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

def get_date_regex_elements(dt, at_word_boundaries_only=False):
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
    sep = "[\W]*"  # zero or more non-alphanumeric characters...
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


def get_code_regex_elements(s, liberal=True, at_word_boundaries_only=True):
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
    if liberal:
        separators = "[\W]*"  # zero or more non-alphanumeric characters...
        s = separators.join([c for c in s])  # ... can appear anywhere
    if at_word_boundaries_only:
        return [WB + s + WB]
    else:
        return [s]


def get_number_of_length_n_regex_elements(n, liberal=True,
                                          at_word_boundaries_only=True):
    """
    Get a list of regex strings for scrubbing n-digit numbers -- for
    example, to remove all 10-digit numbers as putative NHS numbers, or all
    11-digit numbers as putative UK phone numbers.
    """
    s = ["[0-9]"] * n
    if liberal:
        separators = "[\W]*"  # zero or more non-alphanumeric characters...
    else:
        separators = ""
    s = separators.join([c for c in s])
    if at_word_boundaries_only:
        return [WB + s + WB]
    else:
        return [s]


def get_uk_postcode_regex_elements(at_word_boundaries_only=True):
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
        e[i] = e[i].replace(" ", "\s*")  # zero or more whitespace chars
        if at_word_boundaries_only:
            e[i] = WB + e[i] + WB
    return e


def get_string_regex_elements(s, suffixes=None, at_word_boundaries_only=True,
                              max_errors=0):
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


def get_phrase_regex_elements(phrase, at_word_boundaries_only=True,
                              max_errors=0):
    """
    phrase: e.g. '4 Privet Drive'
    """
    strings = get_anon_fragments_from_string(phrase)
    if not strings:
        return
    strings = [escape_literal_string_for_regex(x) for x in strings]
    s = "[\W]+".join(strings)  # 1 or more non-alphanumeric character
    if max_errors > 0:
        s = "(" + s + "){e<" + str(max_errors + 1) + "}"
    if at_word_boundaries_only:
        return [WB + s + WB]
    else:
        return [s]


# =============================================================================
# Combining regex elements into a giant regex
# =============================================================================

def get_regex_string_from_elements(elementlist):
    """
    Convert a list of regex elements into a single regex string.
    """
    if not elementlist:
        return ""
    return u"|".join(elementlist)
    # The or operator | has the lowest precedence.
    # ... http://www.regular-expressions.info/alternation.html
    # We also want to minimize the number of brackets.
    # THEREFORE, ANYTHING CONTRIBUTING FRAGMENTS HERE SHOULD NOT HAVE |
    # OPERATORS AT ITS TOP LEVEL. If it does, it should encapsulate them in a
    # non-capturing group, (?:...)


def get_regex_from_elements(elementlist):
    """
    Convert a list of regex elements into a compiled regex, which will operate
    in case-insensitive fashion on Unicode strings.
    """
    if not elementlist:
        return None
    try:
        s = get_regex_string_from_elements(elementlist)
        return regex.compile(s, regex.IGNORECASE | regex.UNICODE)
    except:
        log.exception("Failed regex: elementlist={}".format(elementlist))
        raise


# Testing:
if False:
    TEST_REGEXES = '''
from __future__ import print_function
import calendar
import dateutil.parser
import regex

import logging
logging.basicConfig()  # just in case nobody else has done this
logger = logging.getLogger("anonymise")

testnumber = 34
testnumber_as_text = "123456"
testdate = dateutil.parser.parse("7 Jan 2013")
teststring = "mother"
testphrase = "348 or 834"
old_testdate = dateutil.parser.parse("3 Sep 1847")

s = u"""

SHOULD REPLACE:
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
    Some postcodes:
        M1 1AA
        M60 1NW
        CR2 6XH
        DN55 1PT
        W1A 1HQ
        EC1A 1BB
"""

regex_date = get_regex_from_elements(get_date_regex_elements(testdate))
regex_number = get_regex_from_elements(
    get_code_regex_elements(str(testnumber)))
regex_number_as_text = get_regex_from_elements(
    get_code_regex_elements(
        get_digit_string_from_vaguely_numeric_string(testnumber_as_text)))
regex_string = get_regex_from_elements(get_string_regex_elements(teststring))
regex_phrase = get_regex_from_elements(get_phrase_regex_elements(testphrase))
regex_10digit = get_regex_from_elements(
    get_number_of_length_n_regex_elements(10))
regex_postcode = get_regex_from_elements(get_uk_postcode_regex_elements())
all_elements = (
    get_date_regex_elements(testdate)
    + get_code_regex_elements(str(testnumber))
    + get_code_regex_elements(
        get_digit_string_from_vaguely_numeric_string(testnumber_as_text))
    + get_string_regex_elements(teststring)
    + get_phrase_regex_elements(testphrase)
    + get_number_of_length_n_regex_elements(10)
    + get_uk_postcode_regex_elements()
)
regex_all = get_regex_from_elements(all_elements)
print(regex_date.sub("DATE_GONE", s))
print(regex_number.sub("NUMBER_GONE", s))
print(regex_number_as_text.sub("NUMBER_AS_TEXT_GONE", s))
print(regex_string.sub("STRING_GONE", s))
print(regex_phrase.sub("PHRASE_GONE", s))
print(regex_10digit.sub("TEN_DIGIT_NUMBERS_GONE", s))
print(regex_postcode.sub("POSTCODES_GONE", s))
print(regex_all.sub("EVERYTHING_GONE", s))
print(get_regex_string_from_elements(all_elements))
print(get_regex_string_from_elements(get_date_regex_elements(testdate)))
print(get_regex_string_from_elements(get_date_regex_elements(old_testdate)))
print(get_regex_string_from_elements(get_phrase_regex_elements(testphrase)))
'''
