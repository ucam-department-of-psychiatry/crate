#!/usr/bin/env python

"""
crate_anon/nlp_manager/tests/scrub_tests.py

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

import logging
from unittest import TestCase

from cardinal_pythonlib.hash import HmacMD5Hasher

from crate_anon.anonymise.constants import ScrubMethod
from crate_anon.anonymise.scrub import PersonalizedScrubber

log = logging.getLogger(__name__)


_TEST_FLASHTEXT = r"""

import flashtext
replacement = "[~~~]"
keywords = [


"""


class PersonalizedScrubberTests(TestCase):
    def setUp(self) -> None:
        self.key = "hello"
        self.hasher = HmacMD5Hasher(self.key)
        self.anonpatient = "[XXX]"
        self.anonthird = "[YYY]"

    def test_phrase_unless_numeric(self) -> None:
        tests = [
            ("5", {
                "blah 5 blah": "blah 5 blah",
            }),
            (" 5 ", {
                "blah 5 blah": "blah 5 blah",
            }),
            (" 5.0 ", {
                "blah 5 blah": "blah 5 blah",
                "blah 5. blah": "blah 5. blah",
                "blah 5.0 blah": "blah 5.0 blah",
            }),
            (" 5. ", {
                "blah 5 blah": "blah 5 blah",
                "blah 5. blah": "blah 5. blah",
                "blah 5.0 blah": "blah 5.0 blah",
            }),
            ("5 Tree Road", {
                "blah 5 blah": "blah 5 blah",
                "blah 5 Tree Road blah": f"blah {self.anonpatient} blah",
            }),
            (" 5 Tree Road ", {
                "blah 5 blah": "blah 5 blah",
                "blah 5 Tree Road blah": f"blah {self.anonpatient} blah",
            }),
            (" 5b ", {
                "blah 5b blah": f"blah {self.anonpatient} blah",
            }),
        ]
        for scrubvalue, mapping in tests:
            scrubber = PersonalizedScrubber(
                replacement_text_patient=self.anonpatient,
                replacement_text_third_party=self.anonthird,
                hasher=self.hasher,
                min_string_length_to_scrub_with=1,
                debug=True
            )
            scrubber.add_value(scrubvalue,
                               scrub_method=ScrubMethod.PHRASE_UNLESS_NUMERIC)
            for start, end in mapping.items():
                self.assertEqual(
                    scrubber.scrub(start),
                    end,
                    f"Failure for scrubvalue: {scrubvalue!r}; regex elements "
                    f"are {scrubber.re_patient_elements}"
                )
