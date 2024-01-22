#!/usr/bin/env python

"""
crate_anon/nlp_manager/tests/regex_numbers_tests.py

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

from crate_anon.nlp_manager.regex_numbers import (
    MINUS_SIGN,
    MULTIPLY,
    PLUS_SIGN,
    POWER,
    POWER_INC_E,
    # POWER_INC_E_ASTERISK,
    SIGN,
    BILLION,
    TRILLION,
    PLAIN_INTEGER,
    PLAIN_INTEGER_W_THOUSAND_COMMAS,
    SCIENTIFIC_NOTATION_EXPONENT,
    IGNORESIGN_FLOAT,
    IGNORESIGN_INTEGER,
    LIBERAL_NUMBER,
    SIGNED_FLOAT,
    SIGNED_INTEGER,
    UNSIGNED_FLOAT,
    UNSIGNED_INTEGER,
)
from crate_anon.nlp_manager.tests.regex_test_helperfunc import (
    assert_text_regex,
)


# =============================================================================
# Unit tests
# =============================================================================


class NumberRegexesTests(unittest.TestCase):
    @staticmethod
    def test_number_regexes() -> None:
        verbose = True

        # ---------------------------------------------------------------------
        # Operators, etc.
        # ---------------------------------------------------------------------
        assert_text_regex(
            "MULTIPLY",
            MULTIPLY,
            [
                ("a * b", ["*"]),
                ("a x b", ["x"]),
                ("a × b", ["×"]),
                ("a ⋅ b", ["⋅"]),
                ("a blah b", []),
            ],
            verbose=verbose,
        )
        assert_text_regex(
            "POWER",
            POWER,
            [
                ("a ^ b", ["^"]),
                ("a ** b", ["**"]),
                ("10e5", []),
                ("10E5", []),
                ("a blah b", []),
            ],
            verbose=verbose,
        )
        assert_text_regex(
            "POWER_INC_E",
            POWER_INC_E,
            [
                ("a ^ b", ["^"]),
                ("a ** b", ["**"]),
                ("10e5", ["e"]),
                ("10E5", ["E"]),
                ("a blah b", []),
            ],
            verbose=verbose,
        )
        assert_text_regex(
            "BILLION",
            BILLION,
            [
                ("10 x 10^9/l", ["x 10^9"]),
            ],
            verbose=verbose,
        )
        assert_text_regex(
            "PLUS_SIGN",
            PLUS_SIGN,
            [
                ("a + b", ["+"]),
                ("a blah b", []),
            ],
            verbose=verbose,
        )
        assert_text_regex(
            "MINUS_SIGN",
            MINUS_SIGN,
            [
                # good:
                ("a - b", ["-"]),  # ASCII hyphen-minus
                ("a − b", ["−"]),  # Unicode minus
                ("a – b", ["–"]),  # en dash
                # bad:
                ("a — b", []),  # em dash
                ("a ‐ b", []),  # Unicode formal hyphen
                ("a blah b", []),
            ],
            verbose=verbose,
        )
        # Can't test optional regexes very easily! They match nothing.
        assert_text_regex(
            "SIGN",
            SIGN,
            [
                # good:
                ("a + b", ["+"]),
                ("a - b", ["-"]),  # ASCII hyphen-minus
                ("a − b", ["−"]),  # Unicode minus
                ("a – b", ["–"]),  # en dash
                # bad:
                ("a — b", []),  # em dash
                ("a ‐ b", []),  # Unicode formal hyphen
                ("a blah b", []),
            ],
            verbose=verbose,
        )

        # ---------------------------------------------------------------------
        # Quantities
        # ---------------------------------------------------------------------

        assert_text_regex(
            "BILLION",
            BILLION,
            [
                ("* 10^9", ["* 10^9"]),
                ("× 10e9", ["× 10e9"]),
                ("x 10 ** 9", ["x 10 ** 9"]),
            ],
            verbose=verbose,
        )
        assert_text_regex(
            "TRILLION",
            TRILLION,
            [
                ("* 10^12", ["* 10^12"]),
                ("× 10e12", ["× 10e12"]),
                ("x 10 ** 12", ["x 10 ** 12"]),
            ],
            verbose=verbose,
        )

        # ---------------------------------------------------------------------
        # Number elements
        # ---------------------------------------------------------------------

        assert_text_regex(
            "PLAIN_INTEGER",
            PLAIN_INTEGER,
            [
                ("a 1234 b", ["1234"]),
                ("a 1234.5 b", ["1234", "5"]),
                ("a 12,000 b", ["12", "000"]),
            ],
            verbose=verbose,
        )
        assert_text_regex(
            "PLAIN_INTEGER_W_THOUSAND_COMMAS",
            PLAIN_INTEGER_W_THOUSAND_COMMAS,
            [
                ("a 1234 b", ["1234"]),
                ("a 1234.5 b", ["1234", "5"]),
                ("a 12,000 b", ["12,000"]),
            ],
            verbose=verbose,
        )
        assert_text_regex(
            "SCIENTIFIC_NOTATION_EXPONENT",
            SCIENTIFIC_NOTATION_EXPONENT,
            [
                ("a 1234 b", []),
                ("E-4", ["E-4"]),
                ("e15", ["e15"]),
                ("e15.3", ["e15"]),
            ],
            verbose=verbose,
        )

        # ---------------------------------------------------------------------
        # Number types
        # ---------------------------------------------------------------------

        assert_text_regex(
            "IGNORESIGN_FLOAT",
            IGNORESIGN_FLOAT,
            [
                ("1", ["1"]),
                ("12345", ["12345"]),
                ("-1", ["1"]),  # NB may be unexpected!
                ("1.2", ["1.2"]),
                ("-3.4", ["3.4"]),  # NB may be unexpected!
                ("+3.4", ["3.4"]),
                ("-3.4e27.3", ["3.4", "27.3"]),
                ("3.4e-27", ["3.4", "27"]),
                ("9,800", ["9,800"]),
                ("17,600.34", ["17,600.34"]),
                ("-17,300.6588", ["17,300.6588"]),
                ("+12345", ["12345"]),
                ("-12345", ["12345"]),  # NB may be unexpected!
                ("-12345.67", ["12345.67"]),  # NB may be unexpected!
                ("12345.67", ["12345.67"]),
                ("-12345.67e-5", ["12345.67", "5"]),  # NB may be unexpected!
                ("12345.67e-5", ["12345.67", "5"]),  # NB may be unexpected!
            ],
            verbose=verbose,
        )
        assert_text_regex(
            "IGNORESIGN_INTEGER",
            IGNORESIGN_INTEGER,
            [
                ("1", ["1"]),
                ("12345", ["12345"]),
                ("-1", ["1"]),  # will drop sign
                ("1.2", ["1", "2"]),
                ("-3.4", ["3", "4"]),
                ("+3.4", ["3", "4"]),
                ("-3.4e27.3", ["3", "4", "27", "3"]),
                ("3.4e-27", ["3", "4", "27"]),
                ("9,800", ["9,800"]),
                ("17,600.34", ["17,600", "34"]),
                ("-17,300.6588", ["17,300", "6588"]),
                ("-12345", ["12345"]),  # NB may be unexpected!
                ("-12345.67", ["12345", "67"]),  # NB may be unexpected!
            ],
            verbose=verbose,
        )
        assert_text_regex(
            "LIBERAL_NUMBER",
            LIBERAL_NUMBER,
            [
                ("1", ["1"]),
                ("12345", ["12345"]),
                ("-1", ["-1"]),
                ("1.2", ["1.2"]),
                ("-3.4", ["-3.4"]),
                ("+3.4", ["+3.4"]),
                (
                    "-3.4e27.3",
                    ["-3.4e27", "3"],
                ),  # not valid scientific notation
                ("3.4e-27", ["3.4e-27"]),
                ("9,800", ["9,800"]),
                ("17,600.34", ["17,600.34"]),
                ("-17,300.6588", ["-17,300.6588"]),
                ("+12345", ["+12345"]),
                ("-12345", ["-12345"]),
                ("-12345.67", ["-12345.67"]),
                ("-12345.67e-5", ["-12345.67e-5"]),
            ],
            verbose=verbose,
        )
        assert_text_regex(
            "SIGNED_FLOAT",
            SIGNED_FLOAT,
            [
                ("1", ["1"]),
                ("12345", ["12345"]),
                ("-1", ["-1"]),
                ("1.2", ["1.2"]),
                ("-3.4", ["-3.4"]),
                ("+3.4", ["+3.4"]),
                ("-3.4e27.3", ["-3.4", "27.3"]),
                ("3.4e-27", ["3.4", "-27"]),
                ("9,800", ["9,800"]),
                ("17,600.34", ["17,600.34"]),
                ("-17,300.6588", ["-17,300.6588"]),
                ("+12345", ["+12345"]),
                ("-12345", ["-12345"]),
                ("-12345.67", ["-12345.67"]),
                ("-12345.67e-5", ["-12345.67", "-5"]),  # NB may be unexpected!
            ],
            verbose=verbose,
        )
        assert_text_regex(
            "SIGNED_INTEGER",
            SIGNED_INTEGER,
            [
                ("1", ["1"]),
                ("12345", ["12345"]),
                ("-1", ["-1"]),
                ("1.2", ["1", "2"]),
                ("-3.4", ["-3", "4"]),
                ("+3.4", ["+3", "4"]),
                ("-3.4e27.3", ["-3", "4", "27", "3"]),
                ("3.4e-27", ["3", "4", "-27"]),
                ("9,800", ["9,800"]),
                ("17,600.34", ["17,600", "34"]),
                ("-17,300.6588", ["-17,300", "6588"]),
                ("+12345", ["+12345"]),
                ("-12345", ["-12345"]),
                ("-12345.67", ["-12345", "67"]),  # NB may be unexpected!
                (
                    "-12345.67e-5",
                    ["-12345", "67", "-5"],
                ),  # NB may be unexpected!
            ],
            verbose=verbose,
        )
        assert_text_regex(
            "UNSIGNED_FLOAT",
            UNSIGNED_FLOAT,
            [
                ("1", ["1"]),
                ("12345", ["12345"]),
                ("-1", []),
                ("1.2", ["1.2"]),
                ("-3.4", []),
                ("+3.4", ["+3.4"]),
                ("-3.4e27.3", ["27.3"]),
                ("3.4e-27", ["3.4"]),
                ("9,800", ["9,800"]),
                ("17,600.34", ["17,600.34"]),
                ("-17,300.6588", []),
                ("+12345", ["+12345"]),
                ("-12345", []),
                ("-12345.67", []),
                ("12345.67", ["12345.67"]),
                ("-12345.67e-5", []),
                ("12345.67e-5", ["12345.67"]),  # NB may be unexpected!
            ],
            verbose=verbose,
        )
        assert_text_regex(
            "UNSIGNED_INTEGER",
            UNSIGNED_INTEGER,
            [
                ("12345", ["12345"]),
                ("+12345", ["+12345"]),
                ("-12345", []),
                ("-12345.67", []),
                ("-12345.67e-5", []),
            ],
            verbose=verbose,
        )
