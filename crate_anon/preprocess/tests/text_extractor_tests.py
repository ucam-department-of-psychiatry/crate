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
from pathlib import Path
import shutil
import tempfile
from unittest import mock

from faker.providers import BaseProvider
from faker_file.storages.filesystem import FileSystemStorage
from sqlalchemy.exc import MultipleResultsFound, NoResultFound

from crate_anon.preprocess.constants import CRATE_TABLE_EXTRACTED_TEXT
from crate_anon.preprocess.systmone_ddgen import S1GenericCol, SystmOneContext
from crate_anon.preprocess.text_extractor import SystmOneTextExtractor
from crate_anon.testing.classes import CrateTestCase


class RowIdentifierProvider(BaseProvider):
    def row_identifier(self) -> int:
        return self.generator.pyint(1_000_000_000, 9_000_000_000)


class DocumentUidProvider(BaseProvider):
    def document_uid(self) -> int:
        return self.generator.pyint(
            0x1000_0000_0000_0000, 0xFFFF_FFFF_FFFF_FFFF
        )


class SubfolderProvider(BaseProvider):
    def subfolder(self) -> int:
        return self.generator.pyint(1, 4)


class IndexProvider(BaseProvider):
    def index(self) -> int:
        return self.generator.pyint(0, 9)


class PatientIdProvider(BaseProvider):
    def patient_id(self) -> int:
        return self.generator.pyint(1, 10_000_000)


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

        self.mock_document_to_text = mock.Mock()
        self.mock_last_extracted = self.fake.past_datetime()
        self.mock_values = mock.Mock()
        self.mock_insert_result = mock.Mock(values=self.mock_values)
        self.mock_insert = mock.Mock(return_value=self.mock_insert_result)

        self.register_providers()

    def register_providers(self) -> None:
        self.fake.add_provider(RowIdentifierProvider)
        self.fake.add_provider(DocumentUidProvider)
        self.fake.add_provider(SubfolderProvider)
        self.fake.add_provider(IndexProvider)
        self.fake.add_provider(PatientIdProvider)

    def tearDown(self) -> None:
        shutil.rmtree(self.root_directory)

    def generate_filename(
        self,
        extension: str,
        row_identifier: int = None,
        document_uid: int = None,
        subfolder: int = None,
        index: int = None,
    ) -> str:
        if row_identifier is None:
            row_identifier = self.fake.row_indentifier()

        if document_uid is None:
            document_uid = self.fake.document_uid()

        if subfolder is None:
            subfolder = self.fake.subfolder()

        if index is None:
            index = self.fake.index()

        return f"{row_identifier}_{document_uid:x}_{subfolder}_{index}.{extension}"  # noqa: E501

    def test_unknown_row_identifier_skipped(self) -> None:
        content = self.fake.paragraph(nb_sentences=10)
        row_identifier = self.fake.row_identifier()
        filename = os.path.join(
            self.root_directory,
            self.generate_filename("txt", row_identifier=row_identifier),
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
                f"... no row found for RowIdentifier: {row_identifier}",
                logging_cm,
            )

    def test_multiple_results_skipped(self) -> None:
        # Not seen in the real world but theoretically possible.
        content = self.fake.paragraph(nb_sentences=10)
        row_identifier = self.fake.row_identifier()
        filename = os.path.join(
            self.root_directory,
            self.generate_filename("txt", row_identifier=row_identifier),
        )
        self.storage.write_text(filename, content)

        with mock.patch.multiple(
            "crate_anon.preprocess.text_extractor",
            select=self.mock_select_fn,
        ):
            self.mock_one.side_effect = MultipleResultsFound()
            with self.assertLogs(level=logging.ERROR) as logging_cm:
                self.extractor.extract_all()

            self.assert_logged(
                "crate_anon.preprocess.text_extractor",
                logging.ERROR,
                (
                    "... multiple rows found with RowIdentifier: "
                    f"{row_identifier}"
                ),
                logging_cm,
            )

    def test_row_inserted_into_table(self) -> None:
        content = self.fake.paragraph(nb_sentences=10)
        row_identifier = self.fake.row_identifier()
        document_uid = self.fake.document_uid()
        filename = os.path.join(
            self.root_directory,
            self.generate_filename(
                "txt", row_identifier=row_identifier, document_uid=document_uid
            ),
        )
        self.storage.write_text(filename, content)

        patient_id = self.fake.patient_id()
        self.mock_one.return_value = mock.Mock(
            _mapping={
                S1GenericCol.PATIENT_ID: patient_id,
            }
        )
        self.mock_document_to_text.return_value = content

        with mock.patch.multiple(
            "crate_anon.preprocess.text_extractor",
            select=self.mock_select_fn,
            document_to_text=self.mock_document_to_text,
            Pendulum=mock.Mock(
                now=mock.Mock(return_value=self.mock_last_extracted)
            ),
            insert=self.mock_insert,
        ):
            self.extractor.extract_all()

        values = dict(
            RowIdentifier=row_identifier,
            DocumentUID=f"{document_uid:x}",
            IDPatient=patient_id,
            crate_file_path=str(Path(*Path(filename).parts[-2:])),
            crate_text=content,
            crate_text_last_extracted=self.mock_last_extracted,
        )

        self.mock_values.assert_called_once_with(**values)
