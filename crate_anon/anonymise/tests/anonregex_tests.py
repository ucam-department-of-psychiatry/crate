#!/usr/bin/env python

"""
crate_anon/anonymise/tests/anonregex_tests.py

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

Unit testing.

"""

# =============================================================================
# Imports
# =============================================================================

from datetime import date
import dateutil.parser  # for unit tests
import logging
from typing import List, Tuple
from unittest import TestCase

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
import regex

from crate_anon.anonymise.anonregex import (
    get_anon_fragments_from_string,
    get_code_regex_elements,
    get_date_regex_elements,
    get_generic_date_regex_elements,
    get_number_of_length_n_regex_elements,
    get_phrase_regex_elements,
    get_regex_from_elements,
    get_regex_string_from_elements,
    get_string_regex_elements,
    get_uk_postcode_regex_elements,
    get_uk_postcode_regex_string,
)
from crate_anon.common.stringfunc import (
    get_digit_string_from_vaguely_numeric_string,
    reduce_to_alphanumeric,
)

log = logging.getLogger(__name__)


# =============================================================================
# Test anonymisation regexes
# =============================================================================


class TestAnonRegexes(TestCase):
    """
    Unit tests.
    """

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
            get_code_regex_elements(str(testnumber))
        )
        regex_number_as_text = get_regex_from_elements(
            get_code_regex_elements(
                get_digit_string_from_vaguely_numeric_string(
                    testnumber_as_text
                )
            )
        )
        regex_string = get_regex_from_elements(
            get_string_regex_elements(teststring)
        )
        regex_email = get_regex_from_elements(
            get_string_regex_elements(testemail)
        )
        regex_phrase = get_regex_from_elements(
            get_phrase_regex_elements(testphrase)
        )
        regex_10digit = get_regex_from_elements(
            get_number_of_length_n_regex_elements(10)
        )
        regex_postcode = get_regex_from_elements(
            get_uk_postcode_regex_elements()
        )
        all_elements = (
            get_date_regex_elements(testdate)
            + get_code_regex_elements(str(testnumber))
            + get_code_regex_elements(
                get_digit_string_from_vaguely_numeric_string(
                    testnumber_as_text
                )
            )
            + get_string_regex_elements(teststring)
            + get_string_regex_elements(testemail)
            + get_phrase_regex_elements(testphrase)
            + get_number_of_length_n_regex_elements(10)
            + get_uk_postcode_regex_elements()
        )
        regex_all = get_regex_from_elements(all_elements)

        self.report(
            "Removing date: " + testdate_str, regex_date.sub("DATE_GONE", s)
        )
        self.report(
            f"Removing number: {testnumber}",
            regex_number.sub("NUMBER_GONE", s),
        )
        self.report(
            "Removing numbers as text: " + testnumber_as_text,
            regex_number_as_text.sub("NUMBER_AS_TEXT_GONE", s),
        )
        self.report(
            "Removing string: " + teststring,
            regex_string.sub("STRING_GONE", s),
        )
        self.report(
            "Removing email: " + testemail, regex_email.sub("EMAIL_GONE", s)
        )
        self.report(
            "Removing phrase: " + testphrase,
            regex_phrase.sub("PHRASE_GONE", s),
        )
        self.report(
            "Removing 10-digit numbers",
            regex_10digit.sub("TEN_DIGIT_NUMBERS_GONE", s),
        )
        self.report(
            "Removing postcodes", regex_postcode.sub("POSTCODES_GONE", s)
        )
        self.report("Removing everything", regex_all.sub("EVERYTHING_GONE", s))
        self.report(
            "All-elements regex", get_regex_string_from_elements(all_elements)
        )
        self.report(
            "Date regex",
            get_regex_string_from_elements(get_date_regex_elements(testdate)),
        )
        self.report(
            "Date regex for 19th century",
            get_regex_string_from_elements(
                get_date_regex_elements(old_testdate)
            ),
        )
        self.report(
            "Phrase regex",
            get_regex_string_from_elements(
                get_phrase_regex_elements(testphrase)
            ),
        )
        self.report(
            "10-digit-number regex",
            get_regex_string_from_elements(
                get_number_of_length_n_regex_elements(10)
            ),
        )

    def test_generic_date(self) -> None:
        # https://stackoverflow.com/questions/51224/regular-expression-to-match-valid-dates  # noqa
        valid = (
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            # From that StackOverflow set
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            # Day, month, year
            "2/11/73",
            "02/11/1973",
            "2/1/73",
            "02/01/73",
            "31/1/1973",
            "02/1/1973",
            "31.1.2011",
            "31-1-2001",
            "29/2/1973",
            "29/02/1976",
            "03/06/2010",
            "12/6/90",
            # month, day, year
            "02/24/1975",
            "06/19/66",
            "03.31.1991",
            "2.29.2003",
            "02-29-55",
            "03-13-55",
            "03-13-1955",
            r"12\24\1974",
            r"12\30\1974",
            r"1\31\1974",
            "03/31/2001",
            "01/21/2001",
            "12/13/2001",
            # Match both DMY and MDY
            "12/12/1978",
            "6/6/78",
            "06/6/1978",
            "6/06/1978",
            # using whitespace as a delimiter
            "13 11 2001",
            "11 13 2001",
            "11 13 01",
            "13 11 01",
            "1 1 01",
            "1 1 2001",
            # Year Month Day order
            "76/02/02",
            "1976/02/29",
            "1976/2/13",
            "76/09/31",
            # YYYYMMDD sortable format
            "19741213",
            "19750101",
            # Valid dates before Epoch
            "12/1/10",
            "12/01/00",
            "12/01/0000",
            # Valid date after 2038
            "01/01/2039",
            "01/01/39",
            # Dates with leading or trailing characters (but still word
            # boundaries)
            "12/31/21/",
            "12/10/2016  8:26:00.39",
            "31/12/1921.10:55",
            # Dates that runs across two lines
            "1/12/19\n74",
            "01/12/19\n74/13/1946",
            "31/12/20\n08:13",
            # Odd but accepted
            "2/12-73",
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            # Extras with our system supporting month words/ordinals
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            "2 Sep 1990",
            "2nd Sep 1990",
            "2 September 1990",
            "02 September 90",
            "2-Sep-90",
            "1990-Sep-02",
            "Sep 2 1990",
            "Sep 2nd 1990",
            "1st Sep 90",
            "1st Sept 2000",
        )
        suboptimal_but_accepted = (
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            # From that StackOverflow set
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            # Invalid, corrupted or nonsense dates
            "74/2/29",  # wasn't a leap year
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            # Extras with our system supporting month words/ordinals
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            "1nd Sep 90",  # ordinal suffix-to-number mapping not checked
        )
        valid_only_without_word_boundaries = (
            # Dates with leading or trailing characters (only recognized if
            # word boundaries not required)
            "31/12/1921AD",
            "wfuwdf12/11/74iuhwf",
            "fwefew13/11/1974",
            "01/12/1974vdwdfwe",
            "01/01/99werwer",
        )
        not_currently_valid_perhaps_should_be = (
            # Valid dates before Epoch
            "12/01/660",
            # Valid date beyond the year 9999
            "01/01/10000",
        )
        invalid = (
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            # From that StackOverflow set
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            # Dates with leading or trailing characters that render it garbage
            "12321301/01/99",
            # Invalid, corrupted or nonsense dates
            "00/01/2100",
            "31/31/2001",
            "101/12/1974",
            # Invalid, corrupted or nonsense dates
            "0/1/2001",
            "1/0/2001",
            "01/0/2001",
            "0101/2001",
            "01/131/2001",
            "56/56/56",
            "00/00/0000",
            "0/0/1999",
            "12/01/0",
            "12/10/-100",
            "12/32/45",
            "20/12/194",
            # Times that look like dates
            "12:13:56",
            "13:12:01",
            "1:12:01PM",
            "1:12:01 AM",
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            # Extras with our system supporting month words/ordinals
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            "1xx Sep 2000",
            "1st Spt 2000",
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            # Irrelevant content
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            "The cat sat on the mat."
            "He started haloperidol 5mg x7/week in 2009.",
        )
        working_valid = valid + suboptimal_but_accepted
        working_invalid = not_currently_valid_perhaps_should_be + invalid

        date_regex_wb_elements = get_generic_date_regex_elements(
            at_word_boundaries_only=True
        )
        date_regex_wb_elements_str = "\n".join(date_regex_wb_elements)
        date_regex_wb = get_regex_from_elements(date_regex_wb_elements)
        date_regex_no_wb_elements = get_generic_date_regex_elements(
            at_word_boundaries_only=False
        )
        date_regex_no_wb_elements_str = "\n".join(date_regex_no_wb_elements)
        date_regex_no_wb = get_regex_from_elements(date_regex_no_wb_elements)

        # match() = at beginning of string
        # search() = anywhere in string
        for x in working_valid:
            self.assertTrue(
                date_regex_wb.search(x),
                f"[#1] Should be recognized as a date (with word "
                f"boundaries) but isn't: {x!r}; "
                f"regex elements =\n{date_regex_wb_elements_str}",
            )
            self.assertTrue(
                date_regex_no_wb.search(x),
                f"[#2] Should be recognized as a date (without word "
                f"boundaries) but isn't: {x!r}; "
                f"regex elements =\n{date_regex_no_wb_elements_str}",
            )
        for x in valid_only_without_word_boundaries:
            self.assertFalse(
                date_regex_wb.search(x),
                f"[#3] Should not be recognized as a date (with word "
                f"boundaries) but is: {x!r}; "
                f"regex elements =\n{date_regex_wb_elements_str}",
            )
            self.assertTrue(
                date_regex_no_wb.search(x),
                f"[#4] Should be recognized as a date (without word "
                f"boundaries) but isn't: {x!r}; "
                f"regex elements =\n{date_regex_no_wb_elements_str}",
            )
        for x in working_invalid:
            self.assertFalse(
                date_regex_wb.search(x),
                f"[#5] Should not be recognized as a date (with word "
                f"boundaries) but is: {x!r}; "
                f"regex elements =\n{date_regex_wb_elements_str}",
            )
            self.assertFalse(
                date_regex_no_wb.search(x),
                f"[#6] Should not be recognized as a date (without word "
                f"boundaries) but is: {x!r}; "
                f"regex elements =\n{date_regex_no_wb_elements_str}",
            )


def examples_for_paper() -> None:
    """
    Examples used in Cardinal (2017),
    https://doi.org/10.1186/s12911-017-0437-1.
    """
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
        words_regexes.extend(
            get_string_regex_elements(
                s,
                suffixes=scrub_string_suffixes,
                at_word_boundaries_only=at_word_boundaries_only,
                max_errors=max_errors,
            )
        )
    print(f"--- For words {testwords}:")
    for r in words_regexes:
        print(r)

    testphrase = "4 Privet Drive"
    phrase_regexes = get_phrase_regex_elements(
        testphrase,
        max_errors=max_errors,
        at_word_boundaries_only=at_word_boundaries_only,
    )
    print(f"--- For phrase {testphrase}:")
    for r in phrase_regexes:
        print(r)

    testnumber = "(01223) 123456"
    anonymise_numbers_at_word_boundaries_only = False
    anonymise_numbers_at_numeric_boundaries_only = True
    number_regexes = get_code_regex_elements(
        get_digit_string_from_vaguely_numeric_string(str(testnumber)),
        at_word_boundaries_only=anonymise_numbers_at_word_boundaries_only,
        at_numeric_boundaries_only=anonymise_numbers_at_numeric_boundaries_only,  # noqa: E501
    )
    print(f"--- For number {testnumber}:")
    for r in number_regexes:
        print(r)

    testcode = "CB12 3DE"
    anonymise_codes_at_word_boundaries_only = True
    code_regexes = get_code_regex_elements(
        reduce_to_alphanumeric(str(testcode)),
        at_word_boundaries_only=anonymise_codes_at_word_boundaries_only,
    )
    print(f"--- For code {testcode}:")
    for r in code_regexes:
        print(r)

    n_digits = 10
    nonspec_10_digit_number_regexes = get_number_of_length_n_regex_elements(
        n_digits,
        at_word_boundaries_only=anonymise_numbers_at_word_boundaries_only,
    )
    print(f"--- NONSPECIFIC: numbers of length {n_digits}:")
    for r in nonspec_10_digit_number_regexes:
        print(r)

    uk_postcode_regexes = get_uk_postcode_regex_elements(
        at_word_boundaries_only=anonymise_codes_at_word_boundaries_only
    )
    print("--- NONSPECIFIC: UK postcodes:")
    for r in uk_postcode_regexes:
        print(r)

    testdate = date(year=2016, month=12, day=31)
    date_regexes = get_date_regex_elements(testdate)
    print(f"--- For date {testdate}:")
    for r in date_regexes:
        print(r)


class AnonRegexTests2(TestCase):
    """
    More tests of regular expressions for anonymisation.
    """

    def _should_match(self, regexes: List[str], string: str) -> None:
        self.assertTrue(
            any(
                # search (match anywhere), not match (match at start)
                regex.search(pattern, string)
                for pattern in regexes
            ),
            f"Failed to match {string!r} against regexes {regexes}",
        )

    def _should_match_all(
        self, regexes: List[str], strings: List[str]
    ) -> None:
        for s in strings:
            self._should_match(regexes, s)

    def _should_not_match(self, regexes: List[str], string: str) -> None:
        self.assertFalse(
            any(
                # search (match anywhere), not match (match at start)
                regex.search(pattern, string)
                for pattern in regexes
            ),
            f"Inappropriately matched {string!r} against regexes {regexes}",
        )

    def _should_not_match_any(
        self, regexes: List[str], strings: List[str]
    ) -> None:
        for s in strings:
            self._should_not_match(regexes, s)

    def test_fragments(self) -> None:
        self.assertEqual(
            get_anon_fragments_from_string("John Smith"), ["John", "Smith"]
        )
        self.assertEqual(
            get_anon_fragments_from_string("John D'Souza"),
            ["John", "D", "Souza"],
        )
        self.assertEqual(
            get_anon_fragments_from_string("  42 West Street  "),
            ["42", "West", "Street"],
        )

    def test_date(self) -> None:
        tests = [
            (
                date(2021, 12, 31),
                [
                    # Numeric:
                    "2021-12-31",
                    "31/12/2021",
                    "31/12/21",
                    "12/31/2021",  # American
                    "12/31/21",  # American
                    # Partly textual:
                    "31 Dec 2021",
                    "31 December 2021",
                    "31 December, 2021",
                    "December 31 2021",
                    "December 31, 2021",
                ],
            ),
            (
                date(1980, 5, 6),
                [
                    # Numeric:
                    "1980-05-06",
                    "6/5/1980",
                    "6/5/80",
                    "06/05/1980",
                    "5/6/80",  # American
                    # Partly textual:
                    "6 May 1980",
                    "May 6, 80",
                ],
            ),
        ]  # type: List[Tuple[date, List[str]]]
        for testdate, text_versions in tests:
            regexes = get_date_regex_elements(testdate)
            for text in text_versions:
                self._should_match(regexes, text)

    def test_code_whitespace(self) -> None:
        tests = [
            (
                "PE123AB",
                [
                    "        PE123AB  ",
                    "PE12 3AB",
                    "PE 12 3 AB",
                ],
            ),
            (
                "PE 12 3AB",
                [
                    "        PE123AB  ",
                    "PE12 3AB",
                    "PE 12 3 AB",
                ],
            ),
        ]  # type: List[Tuple[str, List[str]]]
        for testcode, text_versions in tests:
            regexes = get_code_regex_elements(reduce_to_alphanumeric(testcode))
            for text in text_versions:
                self._should_match(regexes, text)

    def test_code_boundaries(self) -> None:
        code = "ABC123"

        word_boundaries = get_code_regex_elements(
            code,
            liberal=False,
            very_liberal=False,
            at_word_boundaries_only=True,
        )
        self._should_match_all(
            word_boundaries,
            [
                f"pq {code} xy",
                f"pq,{code},xy",
                f"12 {code} 34",
                f"12,{code},34",
            ],
        )
        self._should_not_match_any(
            word_boundaries,
            [
                f"pq{code}xy",
                f"pq{code} xy",
                f"pq {code}xy",
                f"12{code}34",
                f"12{code} 34",
                f"12 {code}34",
            ],
        )

        number_boundaries = get_code_regex_elements(
            code,
            liberal=False,
            very_liberal=False,
            at_word_boundaries_only=False,
            at_numeric_boundaries_only=True,
        )
        self._should_match_all(
            number_boundaries,
            [
                f"pq {code} xy",
                f"pq,{code},xy",
                f"12 {code} 34",
                f"12,{code},34",
                f"pq{code}xy",
                f"pq{code} xy",
                f"pq {code}xy",
            ],
        )
        self._should_not_match_any(
            number_boundaries,
            [
                f"12{code}34",
                f"12{code} 34",
                f"12 {code}34",
            ],
        )

        anywhere = get_code_regex_elements(
            code,
            liberal=False,
            very_liberal=False,
            at_word_boundaries_only=False,
            at_numeric_boundaries_only=False,
        )
        self._should_match_all(
            anywhere,
            [
                f"pq {code} xy",
                f"pq,{code},xy",
                f"12 {code} 34",
                f"12,{code},34",
                f"pq{code}xy",
                f"pq{code} xy",
                f"pq {code}xy",
                f"12{code}34",
                f"12{code} 34",
                f"12 {code}34",
            ],
        )

    def test_uk_postcodes(self) -> None:
        """
        Ensure we detect postcodes properly.
        """
        valid_postcodes = [
            # from https://www.mrs.org.uk/pdf/postcodeformat.pdf
            "M1 1AA",
            "M60 1NW",
            "CR2 6XH",
            "DN55 1PT",
            "W1A 1HQ",
            "EC1A 1BB",
            # Some of our institutional postcodes:
            "CB2 0QQ",
        ]
        # See also
        # https://club.ministryoftesting.com/t/fun-postcodes-to-use-when-testing/10772  # noqa
        invalid_postcodes = [
            "ABCDEFG",
        ]
        postcode_regex = regex.compile(
            get_uk_postcode_regex_string(at_word_boundaries_only=False)
        )
        for v in valid_postcodes:
            self.assertTrue(postcode_regex.match(v))
        for i in invalid_postcodes:
            self.assertFalse(postcode_regex.match(i))


if __name__ == "__main__":
    main_only_quicksetup_rootlogger(level=logging.DEBUG)
    examples_for_paper()
