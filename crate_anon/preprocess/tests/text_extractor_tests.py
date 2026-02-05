"""
crate_anon/preprocess/tests/text_extractor_tests.py

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

**Test text extraction from documents.**

"""

import logging
import os
import shutil
import tempfile
from unittest import mock

from faker_file.storages.filesystem import FileSystemStorage
from sqlalchemy.exc import NoResultFound

from crate_anon.preprocess.constants import CRATE_TABLE_EXTRACTED_TEXT
from crate_anon.preprocess.systmone_ddgen import SystmOneContext
from crate_anon.preprocess.text_extractor import SystmOneTextExtractor
from crate_anon.testing.classes import CrateTestCase


class SystmOneTextExtractorTests(CrateTestCase):
    def setUp(self) -> None:
        super().setUp()

        self.mock_one = mock.Mock()
        self.mock_result = mock.Mock(one=self.mock_one)
        self.mock_execute = mock.Mock(return_value=self.mock_result)
        self.mock_connection = mock.Mock(execute=self.mock_execute)
        self.mock_connect_cm = mock.Mock()
        self.mock_connect_cm.__enter__ = mock.Mock(
            return_value=self.mock_connection
        )
        self.mock_connect_cm.__exit__ = mock.Mock()
        self.mock_connect = mock.Mock(return_value=self.mock_connect_cm)
        self.mock_engine = mock.Mock(connect=self.mock_connect)
        self.mock_s1_documents_table = mock.Mock()
        self.mock_extracted_text_table = mock.Mock()
        self.mock_metadata = mock.Mock(
            tables={
                "S1_Documents": self.mock_s1_documents_table,
                CRATE_TABLE_EXTRACTED_TEXT: self.mock_extracted_text_table,
            }
        )
        self.context = SystmOneContext["cpft_dw"]

        self.root_directory = tempfile.mkdtemp()
        self.storage = FileSystemStorage(
            root_path=self.root_directory,
            rel_path="tmp",
        )

        self.mock_table_class = mock.Mock()

        self.extractor = SystmOneTextExtractor(
            self.mock_engine,
            self.mock_metadata,
            self.context,
            self.root_directory,
        )
        self.mock_select_object = mock.Mock()
        self.mock_select_fn = mock.Mock(return_value=self.mock_select_object)

    def tearDown(self) -> None:
        shutil.rmtree(self.root_directory)

    def test_unknown_row_identifier_skipped(self) -> None:
        content = self.fake.paragraph(nb_sentences=10)
        filename = os.path.join(
            self.root_directory, self.generate_filename("txt")
        )
        self.storage.write_text(filename, content)

        with mock.patch.multiple(
            "crate_anon.preprocess.text_extractor",
            select=self.mock_select_fn,
        ):
            self.mock_one.side_effect = NoResultFound()
            with self.assertLogs(level=logging.ERROR) as logging_cm:
                self.extractor.extract_all()

            self.assert_logged(
                "crate_anon.preprocess.text_extractor",
                logging.ERROR,
                "... no row found for RowIdentifier:",
                logging_cm,
            )

    def generate_filename(self, extension: str) -> str:
        row_identifier = self.fake.pyint(1_000_000_000, 9_000_000_000)
        document_uid = self.fake.pyint(
            0x1000_0000_0000_0000, 0xFFFF_FFFF_FFFF_FFFF
        )

        subfolder = self.fake.pyint(1, 4)
        index = self.fake.pyint(0, 9)

        return f"{row_identifier}_{document_uid:x}_{subfolder}_{index}.{extension}"  # noqa: E501
