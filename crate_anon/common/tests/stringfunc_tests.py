#!/usr/bin/env python

"""
crate_anon/common/tests/stringfunc_tests.py

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

from unittest import TestCase

from crate_anon.common.stringfunc import relevant_for_nlp


# =============================================================================
# Unit tests
# =============================================================================


class StringFuncTests(TestCase):
    def test_relevant_for_nlp(self) -> None:
        # fmt: off
        relevant = [
            "a",
            "hello",
            ".. .. // hello ..",
            "Å, Ä + Ö",  # not just English...
            "Ä",
            "ä",
            "Å",
            "å",
            "É",
            "é",
            "Ö",
            "ö",
        ]
        irrelevant = [
            None,
            "",
            "   ",
            ".. .. // ..",
        ]
        # fmt: on

        for r in relevant:
            self.assertTrue(
                relevant_for_nlp(r),
                f"Should be relevant for NLP but being marked as "
                f"irrelevant: {r!r}",
            )
        for i in irrelevant:
            self.assertFalse(
                relevant_for_nlp(i),
                f"Should be irrelevant for NLP but being marked as "
                f"relevant: {i!r}",
            )
