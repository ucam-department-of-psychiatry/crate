#!/usr/bin/env python

"""
crate_anon/anonymise/tests/scrub_tests.py

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

Unit testing.

"""

# =============================================================================
# Imports
# =============================================================================

import re
import logging
import os
from tempfile import TemporaryDirectory
from typing import List
from unittest import TestCase

from cardinal_pythonlib.hash import HmacMD5Hasher

from crate_anon.anonymise.constants import ScrubMethod
from crate_anon.anonymise.scrub import (
    NonspecificScrubber,
    PersonalizedScrubber,
    WordList,
)
from crate_anon.common.bugfix_flashtext import KeywordProcessorFixed

from faker import Faker

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

TEST_KEY = "hello"
PATIENT_REPLACEMENT = "[XXX]"
THIRD_PARTY_REPLACEMENT = "[YYY]"


# =============================================================================
# Test hashing
# =============================================================================


class HashTests(TestCase):
    def test_str_int_hash_equivalent(self) -> None:
        """
        Hashing an integer and its string equivalent should give the same
        answer.
        """
        hasher = HmacMD5Hasher(TEST_KEY)
        x = 1234567
        y = str(x)
        self.assertEqual(
            hasher.hash(x),
            hasher.hash(y),
            "Hasher providing different answer for str and int",
        )


# =============================================================================
# Test WordList
# =============================================================================


class WordListTests(TestCase):
    def setUp(self) -> None:
        self.tempdir = TemporaryDirectory()
        self.maxDiff = None  # see full differences upon failure

    def _test_flashtext_word_boundaries(self, target: str) -> None:
        anon_text = PATIENT_REPLACEMENT
        ft = KeywordProcessorFixed(case_sensitive=False)
        ft.add_keyword(target, anon_text)
        self.assertEqual(
            # FlashText will replace at word boundaries:
            ft.replace_keywords(f"x {target} x"),
            f"x {anon_text} x",
        )
        self.assertEqual(
            # But only at word boundaries, so this won't replace:
            ft.replace_keywords(f"x{target}x"),
            f"x{target}x",
        )

    def test_flashtext_word_boundaries(self) -> None:
        self._test_flashtext_word_boundaries("daisy")
        self._test_flashtext_word_boundaries("daisy bluebell")

    def _test_wordlist(self, regex_method: bool = False) -> None:
        """
        Test with e.g.

        .. code-block:: python

            pytest -k test_wordlist --log-cli-level=INFO
        """
        denylist_phrases = [
            "Alice",
            "Bob",
            "Charlie Brown",
            "Daisy",
        ]
        anon_text = PATIENT_REPLACEMENT
        test_source_text = """
            I met Alice in the street.
            She was walking with Bob.
            Charlie was not with them.
            Their gloves were brown.
            They stopped to inspect a daisy.
            They discussed Charlie Brown cartoons.
            They discussed Charlie  Brown cartoons all day long.
            They made comment after comment.
        """
        denylist_text = (
            "\n# comment\n"
            + "\n".join(f" {x} " for x in denylist_phrases)
            + "\n"
        )
        # https://stackoverflow.com/questions/952914/how-to-make-a-flat-list-out-of-a-list-of-lists  # noqa
        denylist_words = []  # type: List[str]
        for line in denylist_phrases:
            denylist_words += [x for x in line.split() if x]

        expected_result_phrases = test_source_text
        for element in denylist_phrases:
            # https://stackoverflow.com/questions/919056/case-insensitive-replace  # noqa
            element_re = re.compile(re.escape(element), re.IGNORECASE)
            expected_result_phrases = element_re.sub(
                anon_text, expected_result_phrases
            )
        if regex_method:
            # Regexes handle whitespace flexibly.
            expected_result_phrases = expected_result_phrases.replace(
                "Charlie  Brown", anon_text
            )

        expected_result_words = test_source_text
        for element in denylist_words:
            element_re = re.compile(re.escape(element), re.IGNORECASE)
            expected_result_words = element_re.sub(
                anon_text, expected_result_words
            )

        filename = os.path.join(self.tempdir.name, "badwords.txt")
        with open(filename, "wt") as f:
            f.write(denylist_text)

        wordlist_phrases = WordList(
            filenames=[filename],
            as_phrases=True,
            replacement_text=anon_text,
            regex_method=regex_method,
        )
        wordlist_words = WordList(
            filenames=[filename],
            as_phrases=False,
            replacement_text=anon_text,
            regex_method=regex_method,
        )

        log.info(f"test_source_text: {test_source_text}")
        log.info(f"denylist_text: {denylist_text}")

        result_words = wordlist_words.scrub(test_source_text)
        log.info(f"denylist_words: {denylist_words}")
        log.info(f"result_words: {result_words}")
        log.info(f"expected_result_words: {expected_result_words}")
        self.assertEqual(result_words, expected_result_words)

        result_phrases = wordlist_phrases.scrub(test_source_text)
        log.info(f"denylist_phrases: {denylist_phrases}")
        log.info(f"result_phrases: {result_phrases}")
        log.info(f"expected_result_phrases: {expected_result_phrases}")
        self.assertEqual(result_phrases, expected_result_phrases)

        wordlist_suffixes = WordList(
            words=["one", "two"],
            suffixes=["dog", "cat"],
            replacement_text=anon_text,
            regex_method=regex_method,
        )
        self.assertEqual(
            wordlist_suffixes.scrub("x one x"), f"x {anon_text} x"
        )
        self.assertEqual(
            wordlist_suffixes.scrub("x onedog x"), f"x {anon_text} x"
        )
        self.assertEqual(
            wordlist_suffixes.scrub("x one dog x"), f"x {anon_text} dog x"
        )

    def test_wordlist(self) -> None:
        self._test_wordlist(regex_method=False)
        self._test_wordlist(regex_method=True)


class ScrubberTestCase(TestCase):
    def setUp(self) -> None:
        self.key = TEST_KEY
        self.hasher = HmacMD5Hasher(self.key)


# =============================================================================
# Test PersonalizedScrubber
# =============================================================================


class PersonalizedScrubberTests(ScrubberTestCase):
    def setUp(self) -> None:
        super().setUp()

        self.anonpatient = PATIENT_REPLACEMENT
        self.anonthird = THIRD_PARTY_REPLACEMENT

    def test_phrase_unless_numeric(self) -> None:
        tests = [
            (
                "5",
                {
                    "blah 5 blah": "blah 5 blah",
                },
            ),
            (
                " 5 ",
                {
                    "blah 5 blah": "blah 5 blah",
                },
            ),
            (
                " 5.0 ",
                {
                    "blah 5 blah": "blah 5 blah",
                    "blah 5. blah": "blah 5. blah",
                    "blah 5.0 blah": "blah 5.0 blah",
                },
            ),
            (
                " 5. ",
                {
                    "blah 5 blah": "blah 5 blah",
                    "blah 5. blah": "blah 5. blah",
                    "blah 5.0 blah": "blah 5.0 blah",
                },
            ),
            (
                "5 Tree Road",
                {
                    "blah 5 blah": "blah 5 blah",
                    "blah 5 Tree Road blah": f"blah {self.anonpatient} blah",
                },
            ),
            (
                " 5 Tree Road ",
                {
                    "blah 5 blah": "blah 5 blah",
                    "blah 5 Tree Road blah": f"blah {self.anonpatient} blah",
                },
            ),
            (
                " 5b ",
                {
                    "blah 5b blah": f"blah {self.anonpatient} blah",
                },
            ),
        ]
        for scrubvalue, mapping in tests:
            scrubber = PersonalizedScrubber(
                replacement_text_patient=self.anonpatient,
                replacement_text_third_party=self.anonthird,
                hasher=self.hasher,
                min_string_length_to_scrub_with=1,
                debug=True,
            )
            scrubber.add_value(
                scrubvalue, scrub_method=ScrubMethod.PHRASE_UNLESS_NUMERIC
            )
            for start, end in mapping.items():
                self.assertEqual(
                    scrubber.scrub(start),
                    end,
                    f"Failure for scrubvalue: {scrubvalue!r}; regex elements "
                    f"are {scrubber.re_patient_elements}",
                )


class NonspecificScrubberTests(ScrubberTestCase):
    def setUp(self) -> None:
        super().setUp()

        self.fake = Faker(["en-GB"])
        self.fake.seed_instance(1234)

    def test_all_dates_scrubbed(self) -> None:
        date_of_birth_1 = self.fake.date_of_birth()
        date_string_1 = date_of_birth_1.strftime("%d %b %Y")

        date_of_birth_2 = self.fake.date_of_birth()
        date_string_2 = date_of_birth_2.strftime("%d %b %Y")

        text = (
            f"{self.fake.text()} {date_string_1} "
            f"{self.fake.text()} {date_string_2}"
        )

        scrubber = NonspecificScrubber(
            self.hasher,
            replacement_text_all_dates="[REDACTED]",
            scrub_all_dates=True,
        )

        scrubbed = scrubber.scrub(text)

        self.assertEqual(scrubbed.count("[REDACTED]"), 2)

    def test_all_dates_in_supported_formats_blurred(self) -> None:
        tests = (
            ("01 Feb 2003", "Feb 2003"),
            ("01 Feb 00", "Feb 2000"),
            ("01 Feb 69", "Feb 1969"),
            ("01 Feb 99", "Feb 1999"),
            ("4/5/2006", "May 2006"),
            ("4/5/99", "May 1999"),
            ("7/31/2008", "Jul 2008"),
            ("7/31/99", "Jul 1999"),
            ("8th Sept 2010", "Sep 2010"),
            ("8th Sept 99", "Sep 1999"),
            ("7/31/2008", "Jul 2008"),
            ("7/31/99", "Jul 1999"),
            ("2011-12-13", "Dec 2011"),
            ("99-12-13", "Dec 1999"),
            ("20160718", "Jul 2016"),
        )

        scrubber = NonspecificScrubber(
            self.hasher,
            scrub_all_dates=True,
            replacement_text_all_dates="%b %Y",
        )

        for (text, expected) in tests:
            self.assertEqual(
                scrubber.scrub(text), expected, msg=f"test: {text}"
            )

    def test_non_dates_scrubbed(self) -> None:
        scrubber = NonspecificScrubber(
            self.hasher,
            scrub_all_uk_postcodes=True,
            scrub_all_dates=True,
            replacement_text="[REDACTED]",
            replacement_text_all_dates="%b %Y",
        )

        self.assertEqual(scrubber.scrub(self.fake.postcode()), "[REDACTED]")

    def test_scrub_all_dates_with_replacement(self) -> None:
        custom_placeholder_tests = [
            ("[%Y-%m]", "[2022-02]"),
            ("[%B, %Y]", "[February, 2022]"),
            ("[%b '%y]", "[Feb '22]"),
            ("[%Y]", "[2022]"),
            ("[%b %Y]", "[Feb 2022]"),
        ]

        for (replacement, expected) in custom_placeholder_tests:
            scrubber = NonspecificScrubber(
                self.hasher,
                scrub_all_dates=True,
                replacement_text_all_dates=replacement,
            )

            self.assertEqual(scrubber.scrub("2022-02-28"), expected)

    def test_raises_for_unsupported_date_formats(self) -> None:
        bad_formats = [
            "%a",
            "%A",
            "%w",
            "%d",
            "%H",
            "%I",
            "%p",
            "%M",
            "%S",
            "%f",
            "%z",
            "%Z",
            "%j",
            "%U",
            "%W",
            "%c",
            "%x",
            "%X",
            "%G",
            "%u",
            "%V",
        ]

        for replacement in bad_formats:
            with self.assertRaises(ValueError):
                NonspecificScrubber(
                    self.hasher,
                    scrub_all_dates=True,
                    replacement_text_all_dates=replacement,
                )

    # TODO: Documentation
