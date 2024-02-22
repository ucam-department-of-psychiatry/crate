"""
crate_anon/common/tests/regex_helper_tests.py

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

from unittest import TestCase

from crate_anon.common.regex_helpers import first_n_characters_required


# =============================================================================
# Unit tests
# =============================================================================


class RegexHelperTests(TestCase):
    def test_first_n_characters_required(self) -> None:
        self.assertEqual(first_n_characters_required("abc", 3), "abc")
        self.assertEqual(first_n_characters_required("abc", 4), "abc")
        self.assertEqual(first_n_characters_required("abcd", 3), "abc(?:d)?")
        self.assertEqual(
            first_n_characters_required("abcde", 3), "abc(?:d(?:e)?)?"
        )
