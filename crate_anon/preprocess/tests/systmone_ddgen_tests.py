#!/usr/bin/env python

"""
crate_anon/preprocess/tests/systmone_ddgen_tests.py

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

from crate_anon.preprocess.systmone_ddgen import (
    core_tablename,
    eq,
    eq_re,
    is_free_text,
    is_in_re,
    OMIT_AND_IGNORE_TABLES_REGEX,
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
        cpft = SystmOneContext.CPFT_DW
        test_referralsopen = "S1_ReferralsOpen"  # CPFT version
        test_referralsopen_core = core_tablename(
            tablename=test_referralsopen,
            from_context=cpft,
            allow_unprefixed=True,
        )
        self.assertTrue(eq(test_referralsopen_core, "ReferralsOpen"))
        self.assertTrue(eq_re(test_referralsopen_core, "ReferralsOpen$"))
        omit_tables = OMIT_AND_IGNORE_TABLES_REGEX[cpft]
        self.assertTrue(is_in_re(test_referralsopen_core, omit_tables))
        self.assertTrue(is_in_re("Accommodation_20210329", omit_tables))
        self.assertTrue(is_in_re("Accommodation_20210329_blah", omit_tables))
        self.assertTrue(is_in_re("S1_Accommodation_20210329", omit_tables))

    def test_freetext_columns(self) -> None:
        sre = SystmOneContext.TPP_SRE
        cpft = SystmOneContext.CPFT_DW
        # Free-text columns in all environments:
        for context in [sre, cpft]:
            self.assertTrue(is_free_text("FreeText", "FreeText", context))
        # CPFT but not SRE environment:
        self.assertTrue(
            is_free_text(
                "FreeText_CYPFRS_TelephoneTriage", "RiskofAbsconding", cpft
            )
        )
        self.assertFalse(
            is_free_text(
                "FreeText_CYPFRS_TelephoneTriage", "RiskofAbsconding", sre
            )
        )
        # Not even in CPFT:
        self.assertFalse(
            is_free_text("FreeText_Honos_Scoring_Answers", "FreeText", cpft)
        )
