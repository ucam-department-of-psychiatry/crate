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

import csv
from tempfile import NamedTemporaryFile
from typing import List, TYPE_CHECKING
from unittest import mock, TestCase

from crate_anon.anonymise.dd import DataDictionary
from crate_anon.anonymise.ddr import DataDictionaryRow
from crate_anon.preprocess.systmone_ddgen import (
    core_tablename,
    eq,
    eq_re,
    is_free_text,
    is_in_re,
    modify_dd_for_systmone,
    OMIT_AND_IGNORE_TABLES_REGEX,
    SystmOneContext,
    SystmOneSRESpecRow,
)

if TYPE_CHECKING:
    from crate_anon.anonymise.config import Config


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


class SystmOneDDGenTestCase(TestCase):
    def setUp(self) -> None:
        super().setUp()

        self.src_spec_row_dict = dict(
            TableName="",
            TableDescription="",
            ColumnName="",
            ColumnDescription="",
            ColumnDataType="",
            ColumnLength=0,
            DateDefining="Yes",
            ColumnOrdinal=0,
            LinkedTable="",
            LinkedColumn1="",
            LinkedColumn2="",
        )

        self.context = SystmOneContext.CPFT_DW


class SystmOneSRESpecRowTests(SystmOneDDGenTestCase):
    def test_comment_has_table_and_column_descriptions(self) -> None:
        self.src_spec_row_dict["TableDescription"] = "table_description"
        self.src_spec_row_dict["ColumnDescription"] = "column_description"

        row = SystmOneSRESpecRow(self.src_spec_row_dict)

        self.assertEqual(
            row.comment(self.context),
            "TABLE: table_description // COLUMN: column_description",
        )

    def test_description_has_translated_table_name_column_name_and_comments(
        self,
    ) -> None:
        self.src_spec_row_dict["TableName"] = "SRPatient"
        self.src_spec_row_dict["ColumnName"] = "IDPatient"
        self.src_spec_row_dict["TableDescription"] = "table_description"
        self.src_spec_row_dict["ColumnDescription"] = "column_description"

        row = SystmOneSRESpecRow(self.src_spec_row_dict)

        description = row.description(self.context)
        self.assertEqual(
            description,
            (
                "S1_Patient.IDPatient // "
                "TABLE: table_description // "
                "COLUMN: column_description"
            ),
        )


class TestDataDictionary(DataDictionary):
    def __init__(
        self, config: "Config", rows: List[DataDictionaryRow]
    ) -> None:
        super().__init__(config)

        self.rows = rows


class ModifyDDForSystmOneTests(SystmOneDDGenTestCase):
    def test_table_comments_from_spec_added_to_data_dictionary(self) -> None:
        mock_config = mock.Mock()

        dd_row_1 = DataDictionaryRow(mock_config)
        dd_row_1.src_db = "Source"
        dd_row_1.src_table = "S1_Patient"
        dd_row_1.src_field = "IDPatient"
        dd_row_1.comment = "IDPatient comment"

        dd_row_2 = DataDictionaryRow(mock_config)
        dd_row_2.src_db = "Source"
        dd_row_2.src_table = "S1_Patient"
        dd_row_2.src_field = "NHSNumber"
        dd_row_2.comment = "NHSNumber comment"

        dd = TestDataDictionary(mock_config, [dd_row_1, dd_row_2])

        context = SystmOneContext.CPFT_DW
        with NamedTemporaryFile(delete=False, mode="w") as f:
            fieldnames = self.src_spec_row_dict.keys()
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            spec_row_1 = self.src_spec_row_dict.copy()
            spec_row_1.update(
                TableName="SRPatient",
                ColumnName="IDPatient",
                TableDescription="SRPatient description from spec",
                ColumnDescription="IDPatient description from spec",
            )

            spec_row_2 = self.src_spec_row_dict.copy()
            spec_row_2.update(
                TableName="SRPatient",
                ColumnName="NHSNumber",
                TableDescription="SRPatient description from spec",
                ColumnDescription="NHSNumber description from spec",
            )

            writer.writerow(spec_row_1)
            writer.writerow(spec_row_2)

        with open(f.name, mode="r") as f:
            modify_dd_for_systmone(
                dd, context, sre_spec_csv_filename=f.name, append_comments=True
            )

        self.assertEqual(len(dd.rows), 3)

        # Comment row is sorted to the top
        self.assertEqual(dd.rows[0].comment, "SRPatient description from spec")
        self.assertEqual(
            dd.rows[1].comment,
            (
                "IDPatient comment // "
                "TABLE: SRPatient description from spec // "
                "COLUMN: IDPatient description from spec"
            ),
        )

        self.assertEqual(
            dd.rows[2].comment,
            (
                "NHSNumber comment // "
                "TABLE: SRPatient description from spec // "
                "COLUMN: NHSNumber description from spec"
            ),
        )

    def test_ddr_existing_table_comment_appended_with_spec_description(
        self,
    ) -> None:
        mock_config = mock.Mock()

        dd_row_1 = DataDictionaryRow(mock_config)
        dd_row_1.src_db = "Source"
        dd_row_1.src_table = "S1_Patient"
        dd_row_1.src_field = "IDPatient"
        dd_row_1.comment = "IDPatient comment"

        dd_row_2 = DataDictionaryRow(mock_config)
        dd_row_2.src_db = "Source"
        dd_row_2.src_table = "S1_Patient"
        dd_row_2.src_field = "NHSNumber"
        dd_row_2.comment = "NHSNumber comment"

        dd_row_3 = DataDictionaryRow(mock_config)
        dd_row_3.src_db = "Source"
        dd_row_3.src_table = "S1_Patient"
        dd_row_3.src_field = ""
        dd_row_3.comment = "Existing table comment"

        dd = TestDataDictionary(mock_config, [dd_row_1, dd_row_2, dd_row_3])

        context = SystmOneContext.CPFT_DW
        with NamedTemporaryFile(delete=False, mode="w") as f:
            fieldnames = self.src_spec_row_dict.keys()
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            spec_row_1 = self.src_spec_row_dict.copy()
            spec_row_1.update(
                TableName="SRPatient",
                ColumnName="IDPatient",
                TableDescription="SRPatient description from spec",
                ColumnDescription="IDPatient description from spec",
            )

            spec_row_2 = self.src_spec_row_dict.copy()
            spec_row_2.update(
                TableName="SRPatient",
                ColumnName="NHSNumber",
                TableDescription="SRPatient description from spec",
                ColumnDescription="NHSNumber description from spec",
            )

            writer.writerow(spec_row_1)
            writer.writerow(spec_row_2)

        with open(f.name, mode="r") as f:
            modify_dd_for_systmone(
                dd, context, sre_spec_csv_filename=f.name, append_comments=True
            )

        self.assertEqual(len(dd.rows), 3)

        # Comment row is sorted to the top
        self.assertEqual(
            dd.rows[0].comment,
            "Existing table comment // SRPatient description from spec",
        )
        self.assertEqual(
            dd.rows[1].comment,
            (
                "IDPatient comment // "
                "TABLE: SRPatient description from spec // "
                "COLUMN: IDPatient description from spec"
            ),
        )

        self.assertEqual(
            dd.rows[2].comment,
            (
                "NHSNumber comment // "
                "TABLE: SRPatient description from spec // "
                "COLUMN: NHSNumber description from spec"
            ),
        )
