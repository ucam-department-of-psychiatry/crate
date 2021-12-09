#!/usr/bin/env python

"""
crate_anon/common/tests/spreadsheet_tests.py

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

import datetime
import tempfile
import os
from unittest import TestCase

from crate_anon.common.spreadsheet import write_spreadsheet


# =============================================================================
# Unit tests
# =============================================================================

class SpreadsheetTests(TestCase):
    # noinspection PyMethodMayBeStatic
    def test_write_values(self) -> None:
        """
        Test that all kinds of types of values can be written to all our
        spreadsheet formats.
        """
        data = {
            "sheet_P": [
                ["P_heading1", "P_heading2", "P_heading3"],
                ["a", 5, None],
                [3.2, datetime.datetime.now(), "b"],
            ],
            "sheet_Q": [
                ["Q_heading1", "Q_heading2", "Q_heading3"],
                ["a", 5, None],
                [3.2, datetime.datetime.now(), "b"],
            ]
        }
        with tempfile.TemporaryDirectory() as dirname:
            ods_filename = os.path.join(dirname, "test.ods")
            write_spreadsheet(ods_filename, data)

            tsv_filename = os.path.join(dirname, "test.tsv")
            write_spreadsheet(tsv_filename, data)

            xlsx_filename = os.path.join(dirname, "test.tsv")
            write_spreadsheet(xlsx_filename, data)

        # ... the test is that nothing crashes.
