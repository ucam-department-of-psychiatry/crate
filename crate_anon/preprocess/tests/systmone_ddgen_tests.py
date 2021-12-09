#!/usr/bin/env python

"""
crate_anon/preprocess/tests/systmone_ddgen_tests.py

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

from unittest import TestCase

from crate_anon.preprocess.systmone_ddgen import (
    core_tablename,
    eq,
    eq_re,
    is_in_re,
    OMIT_TABLES_REGEX,
    SystmOneContext,
)


# =============================================================================
# Unit tests
# =============================================================================

class SystmOneDDGenTests(TestCase):
    def test_excluded_tables(self) -> None:
        """
        Test some regex functions for excluding tables.
        """
        test_referralsopen = "S1_ReferralsOpen"  # CPFT version
        test_referralsopen_core = core_tablename(
            tablename=test_referralsopen,
            from_context=SystmOneContext.CPFT_DW,
            allow_unprefixed=True
        )
        self.assertTrue(eq(test_referralsopen_core, "ReferralsOpen"))
        self.assertTrue(eq_re(test_referralsopen_core, "ReferralsOpen$"))
        self.assertTrue(is_in_re(test_referralsopen_core, OMIT_TABLES_REGEX))
