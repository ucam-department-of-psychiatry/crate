#!/usr/bin/env python

"""
crate_anon/nlp_manager/tests/parse_cognitive_tests.py

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

import unittest

from crate_anon.nlp_manager.parse_cognitive import (
    ALL_COGNITIVE_NLP,
    ALL_COGNITIVE_VALIDATORS,
)


# =============================================================================
# Unit tests
# =============================================================================


class TestCognitive(unittest.TestCase):
    @staticmethod
    def test_all_cognitive() -> None:
        """
        Test all parsers in this module.
        """
        for cls in ALL_COGNITIVE_NLP:
            cls(None, None).test(verbose=True)
        for cls in ALL_COGNITIVE_VALIDATORS:
            # we want the ACE validator in particular
            cls(None, None).test(verbose=True)
