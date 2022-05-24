#!/usr/bin/env python

"""
crate_anon/nlp_manager/tests/regex_parser_tests.py

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

Unit tests.

"""

import unittest

from crate_anon.nlp_manager.regex_parser import (
    OPTIONAL_POC,
    OPTIONAL_RESULTS_IGNORABLES,
    RELATION,
    TENSE_INDICATOR,
)
from crate_anon.nlp_manager.tests.regex_test_helperfunc import (
    assert_text_regex,
)


# =============================================================================
# Unit tests
# =============================================================================


class TestParserRegexes(unittest.TestCase):
    @staticmethod
    def test_parser_regexes() -> None:
        verbose = True

        # ---------------------------------------------------------------------
        # Things to ignore
        # ---------------------------------------------------------------------

        assert_text_regex(
            "OPTIONAL_RESULTS_IGNORABLES",
            OPTIONAL_RESULTS_IGNORABLES,
            [
                ("(H)", ["(H)", ""]),
                (" (H) ", [" (H) ", ""]),
                (" (H) mg/L", [" (H) ", "", "", "", "L", ""]),
                ("(HH)", ["(HH)", ""]),
                ("(L)", ["(L)", ""]),
                ("(LL)", ["(LL)", ""]),
                ("(*)", ["(*)", ""]),
                ("  |  (H)  |  ", ["  |  (H)  |  ", ""]),
            ],
            verbose=verbose,
        )
        assert_text_regex(
            "OPTIONAL_POC",
            OPTIONAL_POC,
            [
                (", POC", [", POC", ""]),
            ],
        )

        # ---------------------------------------------------------------------
        # Tense indicators
        # ---------------------------------------------------------------------

        assert_text_regex(
            "TENSE_INDICATOR",
            TENSE_INDICATOR,
            [
                ("a is b", ["is"]),
                ("a was b", ["was"]),
                ("a blah b", []),
            ],
            verbose=verbose,
        )

        # ---------------------------------------------------------------------
        # Mathematical relations
        # ---------------------------------------------------------------------

        assert_text_regex(
            "RELATION",
            RELATION,
            [
                ("a < b", ["<"]),
                ("a less than b", ["less than"]),
                ("a <= b", ["<="]),
                ("a = b", ["="]),
                ("a equals b", ["equals"]),
                ("a equal to b", ["equal to"]),
                ("a >= b", [">="]),
                ("a > b", [">"]),
                ("a more than b", ["more than"]),
                ("a greater than b", ["greater than"]),
                ("a blah b", []),
            ],
            verbose=verbose,
        )
