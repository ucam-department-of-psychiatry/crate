"""
crate_anon/anonymise/tests/ddr_tests.py

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

Data Dictionary Row tests

"""

from unittest import mock, TestCase

from sqlalchemy import String

from crate_anon.anonymise.ddr import DataDictionaryRow


class DataDictionaryRowTests(TestCase):
    def test_odd_chars_replaced_in_dest_table(self) -> None:
        mock_config = mock.Mock()
        ddr = DataDictionaryRow(mock_config)
        # unicode n-dash ------------------------v
        test_table = f"A b(c)d/e|f\tg{chr(0x80)}h–i"
        test_field = test_table

        src_datatype_sqltext = ""  # Arbitrary
        src_sqla_coltype = String()
        mock_db_config = mock.Mock(
            bin2text_dict={},
            ddgen_convert_odd_chars_to_underscore=True,
            ddgen_extra_hash_fields={},
            ddgen_filename_to_text_fields=[],
            ddgen_force_lower_case=False,
            ddgen_include_fields=[],
            ddgen_master_pid_fieldname="nhs_num",
            ddgen_min_length_for_scrubbing=50,
            ddgen_omit_fields=[],
            ddgen_patient_opt_out_fields=[],
            ddgen_per_table_pid_field="patient_id",
            ddgen_pid_defining_fieldnames=[],
            ddgen_pk_fields=[],
            ddgen_rename_tables_remove_suffixes=[],
            ddgen_required_scrubsrc_fields=[],
            ddgen_safe_fields_exempt_from_scrubbing=[],
            ddgen_scrubsrc_patient_fields=[],
            ddgen_scrubsrc_thirdparty_fields=[],
            ddgen_scrubsrc_thirdparty_xref_pid_fields=[],
            ddgen_truncate_date_fields=[],
        )
        ddr.set_from_src_db_info(
            "test_db",
            test_table,
            test_field,
            src_datatype_sqltext,
            src_sqla_coltype,
            mock_db_config,
        )

        expected_table = "A_b_c_d_e_f_g_h_i"
        expected_field = expected_table

        self.assertEqual(ddr.dest_table, expected_table)
        self.assertEqual(ddr.dest_field, expected_field)
