#!/usr/bin/env python

"""
crate_anon/linkage/tests/fuzzy_id_match_tests.py

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

Unit tests.

"""

# =============================================================================
# Imports
# =============================================================================

import unittest

from pendulum import Date

from crate_anon.linkage.fuzzy_id_match import TemporalIdentifier


# =============================================================================
# Unit tests
# =============================================================================

class TestTemporalIdentifier(unittest.TestCase):
    """
    Unit tests for :class:`TemporalIdentifier`.
    """

    def test_overlap(self) -> None:
        d1 = Date(2000, 1, 1)
        d2 = Date(2000, 1, 2)
        d3 = Date(2000, 1, 3)
        d4 = Date(2000, 1, 4)
        p = "dummypostcode"
        # Overlaps
        self.assertEqual(
            TemporalIdentifier(p, d1, d2).overlaps(
                TemporalIdentifier(p, d2, d3)),
            True
        )
        self.assertEqual(
            TemporalIdentifier(p, d2, d3).overlaps(
                TemporalIdentifier(p, d1, d2)),
            True
        )
        self.assertEqual(
            TemporalIdentifier(p, d1, d4).overlaps(
                TemporalIdentifier(p, d2, d3)),
            True
        )
        self.assertEqual(
            TemporalIdentifier(p, d1, None).overlaps(
                TemporalIdentifier(p, None, d4)),
            True
        )
        self.assertEqual(
            TemporalIdentifier(p, None, None).overlaps(
                TemporalIdentifier(p, None, None)),
            True
        )
        # Non-overlaps
        self.assertEqual(
            TemporalIdentifier(p, d1, d2).overlaps(
                TemporalIdentifier(p, d3, d4)),
            False
        )
        self.assertEqual(
            TemporalIdentifier(p, None, d1).overlaps(
                TemporalIdentifier(p, d2, None)),
            False
        )
