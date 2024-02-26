"""
crate_anon/nlp_manager/tests/parse_cognitive_tests.py

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

from crate_anon.nlp_manager.parse_cognitive import (
    ALL_COGNITIVE_NLP_AND_VALIDATORS,
)
from crate_anon.nlp_manager.tests.regex_test_helperfunc import (
    run_tests_nlp_and_validator_classes,
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
        run_tests_nlp_and_validator_classes(ALL_COGNITIVE_NLP_AND_VALIDATORS)
        # ... we want the ACE validator in particular
