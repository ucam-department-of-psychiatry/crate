"""
crate_anon/crateweb/nlp_classification/tests/tasks_tests.py

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

Tests for CRATE NLP classification celery tasks.

"""

from unittest import mock

from django.test import override_settings, TestCase

from crate_anon.crateweb.core.constants import (
    NLP_DB_CONNECTION_NAME,
    RESEARCH_DB_CONNECTION_NAME,
)
from crate_anon.crateweb.nlp_classification.tests.factories import (
    ColumnFactory,
    SampleFactory,
    TableDefinitionFactory,
)
from crate_anon.crateweb.nlp_classification.models import (
    SourceRecord,
)
from crate_anon.crateweb.nlp_classification.tasks import (
    create_source_records_from_sample,
)


@override_settings(CRATE_NLP_BATCH_SIZE=1000)
class CreateSourceRecordsFromSampleTests(TestCase):
    def setUp(self) -> None:
        super().setUp()

        # To avoid making real connections to the source and NLP databases.
        self.mock_get_source_table_names = mock.Mock(return_value=[])
        self.mock_get_source_column_names_for_table = mock.Mock(
            return_value=[]
        )
        self.mock_source_fetchall = mock.Mock(return_value=[])
        self.mock_source_db_connection = mock.Mock(
            get_table_names=self.mock_get_source_table_names,
            get_column_names_for_table=self.mock_get_source_column_names_for_table,  # noqa: E501
            fetchall=self.mock_source_fetchall,
            count=mock.Mock(return_value=0),
        )
        self.mock_nlp_fetchall = mock.Mock(return_value=[])

        self.mock_get_nlp_table_names = mock.Mock(return_value=[])
        self.mock_get_nlp_column_names_for_table = mock.Mock(return_value=[])
        self.mock_nlp_db_connection = mock.Mock(
            get_table_names=self.mock_get_nlp_table_names,
            get_column_names_for_table=self.mock_get_nlp_column_names_for_table,  # noqa: E501
            fetchall=self.mock_nlp_fetchall,
        )
        self.mock_sample_get_source_db_connection = mock.Mock(
            return_value=self.mock_source_db_connection
        )
        self.mock_sample_get_nlp_db_connection = mock.Mock(
            return_value=self.mock_nlp_db_connection
        )

    def test_source_records_created(self) -> None:
        self.mock_get_source_table_names.return_value = [
            "blob",
            "note",
            "patient",
        ]
        self.mock_get_source_column_names_for_table.return_value = [
            "_pk",
            "note",
        ]
        self.mock_get_nlp_table_names.return_value = ["bp", "crp", "esr"]
        self.mock_get_nlp_column_names_for_table.return_value = [
            "_pk",
            "_nlpdef",
            "_srcdb",
            "units",
        ]
        self.mock_source_db_connection.count.return_value = 5
        self.mock_source_fetchall.return_value = [(1,), (2,), (3,), (4,), (5,)]
        self.mock_nlp_fetchall.return_value = [(1, 10), (2, 11), (4, 12)]

        source_table_definition = TableDefinitionFactory(
            db_connection_name=RESEARCH_DB_CONNECTION_NAME,
        )
        source_column = ColumnFactory(table_definition=source_table_definition)
        nlp_table_definition = TableDefinitionFactory(
            db_connection_name=NLP_DB_CONNECTION_NAME,
            table_name="crp",
            pk_column_name="_pk",
        )
        sample = SampleFactory(
            source_column=source_column,
            nlp_table_definition=nlp_table_definition,
        )

        with mock.patch.multiple(
            "crate_anon.crateweb.nlp_classification.models.Sample",
            get_source_database_connection=self.mock_sample_get_source_db_connection,  # noqa: E501
            get_nlp_database_connection=self.mock_sample_get_nlp_db_connection,
        ):
            create_source_records_from_sample(sample.pk)

        self.assertTrue(
            SourceRecord.objects.filter(
                source_column=sample.source_column,
                nlp_table_definition=nlp_table_definition,
                source_pk_value=1,
                nlp_pk_value=10,
            ).exists()
        )
        self.assertTrue(
            SourceRecord.objects.filter(
                source_column=sample.source_column,
                nlp_table_definition=nlp_table_definition,
                source_pk_value=2,
                nlp_pk_value=11,
            ).exists()
        )
        self.assertTrue(
            SourceRecord.objects.filter(
                source_column=sample.source_column,
                nlp_table_definition=nlp_table_definition,
                source_pk_value=3,
                nlp_pk_value="",
            ).exists()
        )
        self.assertTrue(
            SourceRecord.objects.filter(
                source_column=sample.source_column,
                nlp_table_definition=nlp_table_definition,
                source_pk_value=4,
                nlp_pk_value=12,
            ).exists()
        )
        self.assertTrue(
            SourceRecord.objects.filter(
                source_column=sample.source_column,
                nlp_table_definition=nlp_table_definition,
                source_pk_value=5,
                nlp_pk_value="",
            ).exists()
        )
