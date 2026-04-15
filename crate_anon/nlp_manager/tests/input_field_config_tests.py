"""
crate_anon/nlp_manager/tests/input_field_config_tests.py

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

"""

from unittest import mock, TestCase

from sqlalchemy import Column, Table

from crate_anon.common.extendedconfigparser import ConfigSection
from crate_anon.nlp_manager.input_field_config import InputFieldConfig
from crate_anon.nlp_manager.nlp_definition import NlpDefinition


class InputFieldConfigTests(TestCase):
    def setUp(self) -> None:
        super().setUp()

        mock_opt_str = mock.Mock(
            side_effect=[
                "test_srcdb",
                "test_srctable",
                "test_srcpkfield",
                "test_srcfield",
                "test_srcdatetimefield",
            ]
        )

        self.mock_config_section = mock.Mock(
            spec=ConfigSection,
            opt_str=mock_opt_str,
        )

        self.mock_nlpdef = mock.Mock(
            spec=NlpDefinition,
            get_config_section=mock.Mock(
                return_value=self.mock_config_section
            ),
        )

        table_columns = [
            Column(name="three"),
            Column(name="five"),
            Column(name="two"),
            Column(name="four"),
            Column(name="one"),
        ]

        self.mock_table = mock.Mock(spec=Table, columns=table_columns)

    def test_get_copy_columns_ordered_by_name(self) -> None:
        mock_copyfields = ["one", "two", "three"]
        mock_indexed_copyfields = []

        mock_opt_multiline = mock.Mock(
            side_effect=[
                mock_copyfields,
                mock_indexed_copyfields,
            ]
        )
        self.mock_config_section.opt_multiline = mock_opt_multiline

        input_field_config = InputFieldConfig(self.mock_nlpdef, "test")

        with mock.patch.multiple(
            "crate_anon.nlp_manager.input_field_config",
            table_or_view_exists=mock.Mock(return_value=True),
            Table=mock.Mock(return_value=self.mock_table),
        ):
            columns = input_field_config.get_copy_columns()

        names = [c.name for c in columns]

        self.assertEqual(names, ["one", "three", "two"])

    def test_get_copy_indexes_ordered_by_name(self) -> None:
        mock_copyfields = ["one", "two", "three"]
        mock_indexed_copyfields = ["one", "two", "three"]

        mock_opt_multiline = mock.Mock(
            side_effect=[
                mock_copyfields,
                mock_indexed_copyfields,
            ]
        )
        self.mock_config_section.opt_multiline = mock_opt_multiline

        input_field_config = InputFieldConfig(self.mock_nlpdef, "test")

        with mock.patch.multiple(
            "crate_anon.nlp_manager.input_field_config",
            table_or_view_exists=mock.Mock(return_value=True),
            Table=mock.Mock(return_value=self.mock_table),
        ):
            indexes = input_field_config.get_copy_indexes()

        names = [i.name for i in indexes]

        self.assertEqual(names, ["idx_one", "idx_three", "idx_two"])
