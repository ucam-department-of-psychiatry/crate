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

from celery_progress.backend import ProgressRecorder
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
from crate_anon.nlp_manager.constants import (
    FN_SRCPKVAL,
)


# Normally batch would be a big number. This ensures we have the iterator
# slicing working correctly
@override_settings(CRATE_NLP_BATCH_SIZE=2)
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
        self.source_table_definition = TableDefinitionFactory(
            db_connection_name=RESEARCH_DB_CONNECTION_NAME,
        )
        self.source_column = ColumnFactory(
            table_definition=self.source_table_definition,
        )
        self.nlp_table_definition = TableDefinitionFactory(
            db_connection_name=NLP_DB_CONNECTION_NAME,
            table_name="crp",
            pk_column_name="_pk",
        )
        self.sample = SampleFactory(
            source_column=self.source_column,
            nlp_table_definition=self.nlp_table_definition,
            search_term="CRP",
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
        self.mock_source_fetchall.return_value = (
            r for r in [(1,), (2,), (3,), (4,), (5,)]
        )
        # Three calls
        self.mock_nlp_fetchall.side_effect = [
            (r for r in [(1, 10), (1, 13), (2, 11)]),
            (r for r in [(4, 12)]),
            (r for r in []),
        ]

        with mock.patch.multiple(
            "crate_anon.crateweb.nlp_classification.models.Sample",
            get_source_database_connection=self.mock_sample_get_source_db_connection,  # noqa: E501
            get_nlp_database_connection=self.mock_sample_get_nlp_db_connection,
        ):
            create_source_records_from_sample(self.sample.pk)

        self.mock_source_fetchall.assert_called_once_with(
            [self.source_table_definition.pk_column_name],
            self.source_table_definition.table_name,
            f"{self.source_column.name} LIKE %s",
            [f"%{self.sample.search_term}%"],
        )

        self.mock_nlp_fetchall.assert_any_call(
            [FN_SRCPKVAL, self.nlp_table_definition.pk_column_name],
            self.nlp_table_definition.table_name,
            where=f"{FN_SRCPKVAL} IN (%s, %s)",
            params=[1, 2],
        )

        self.mock_nlp_fetchall.assert_any_call(
            [FN_SRCPKVAL, self.nlp_table_definition.pk_column_name],
            self.nlp_table_definition.table_name,
            where=f"{FN_SRCPKVAL} IN (%s, %s)",
            params=[3, 4],
        )

        self.mock_nlp_fetchall.assert_any_call(
            [FN_SRCPKVAL, self.nlp_table_definition.pk_column_name],
            self.nlp_table_definition.table_name,
            where=f"{FN_SRCPKVAL} IN (%s)",
            params=[5],
        )

        self.assertTrue(
            SourceRecord.objects.filter(
                sample=self.sample,
                source_pk_value=1,
                nlp_pk_value=10,
            ).exists()
        )
        self.assertTrue(
            SourceRecord.objects.filter(
                sample=self.sample,
                source_pk_value=1,
                nlp_pk_value=13,
            ).exists()
        )
        self.assertTrue(
            SourceRecord.objects.filter(
                sample=self.sample,
                source_pk_value=2,
                nlp_pk_value=11,
            ).exists()
        )
        self.assertTrue(
            SourceRecord.objects.filter(
                sample=self.sample,
                source_pk_value=3,
                nlp_pk_value="",
            ).exists()
        )
        self.assertTrue(
            SourceRecord.objects.filter(
                sample=self.sample,
                source_pk_value=4,
                nlp_pk_value=12,
            ).exists()
        )
        self.assertTrue(
            SourceRecord.objects.filter(
                sample=self.sample,
                source_pk_value=5,
                nlp_pk_value="",
            ).exists()
        )

    def test_progress_updated(self) -> None:
        mock_set_progress = mock.Mock()

        mock_progress_recorder_obj = mock.Mock(
            spec=ProgressRecorder, set_progress=mock_set_progress
        )
        mock_progress_recorder = mock.Mock(
            return_value=mock_progress_recorder_obj
        )

        with mock.patch.multiple(
            "crate_anon.crateweb.nlp_classification.models.Sample",
            get_source_database_connection=self.mock_sample_get_source_db_connection,  # noqa: E501
            get_nlp_database_connection=self.mock_sample_get_nlp_db_connection,
        ):
            with mock.patch.multiple(
                "crate_anon.crateweb.nlp_classification.tasks",
                ProgressRecorder=mock_progress_recorder,
            ):
                create_source_records_from_sample(self.sample.pk)

        mock_set_progress.assert_has_calls(
            [
                mock.call(
                    0, 0, description="Counting rows from the source database"
                ),
                mock.call(
                    0, 0, description="Creating records for classification"
                ),
            ]
        )
