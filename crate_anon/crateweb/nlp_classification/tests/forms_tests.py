"""
crate_anon/crateweb/nlp_classification/tests/forms_tests.py

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

Tests for CRATE NLP classification forms.

"""

from unittest import mock

from django.test import TestCase

from crate_anon.crateweb.core.constants import (
    NLP_DB_CONNECTION_NAME,
    RESEARCH_DB_CONNECTION_NAME,
)
from crate_anon.crateweb.nlp_classification.forms import (
    WizardSelectQuestionForm,
    WizardSelectColumnForm,
    WizardSelectSourceTableDefinitionForm,
    WizardSelectTableForm,
)
from crate_anon.crateweb.nlp_classification.tests.factories import (
    QuestionFactory,
    TableDefinitionFactory,
    TaskFactory,
)


class WizardSelectQuestionFormTests(TestCase):
    def test_not_filtered_by_task_by_default(self) -> None:
        task1 = TaskFactory()
        task2 = TaskFactory()

        q1_1 = QuestionFactory(task=task1)
        q1_2 = QuestionFactory(task=task1)

        q2_1 = QuestionFactory(task=task2)
        q2_2 = QuestionFactory(task=task2)

        form = WizardSelectQuestionForm()

        self.assertQuerySetEqual(
            form.fields["question"].queryset,
            [q1_1, q1_2, q2_1, q2_2],
            ordered=False,
        )

    def test_filtered_by_task(self) -> None:
        task1 = TaskFactory()
        task2 = TaskFactory()

        q1_1 = QuestionFactory(task=task1)
        q1_2 = QuestionFactory(task=task1)

        QuestionFactory(task=task2)
        QuestionFactory(task=task2)

        form = WizardSelectQuestionForm(task=task1)

        self.assertQuerySetEqual(
            form.fields["question"].queryset, [q1_1, q1_2], ordered=False
        )


class WizardSelectSourceTableDefinitionFormTests(TestCase):
    def test_filtered_by_source_db_connection(self) -> None:
        source_td_1 = TableDefinitionFactory(
            db_connection_name=RESEARCH_DB_CONNECTION_NAME
        )
        source_td_2 = TableDefinitionFactory(
            db_connection_name=RESEARCH_DB_CONNECTION_NAME
        )
        TableDefinitionFactory(db_connection_name=NLP_DB_CONNECTION_NAME)

        form = WizardSelectSourceTableDefinitionForm()

        self.assertQuerySetEqual(
            form.fields["table_definition"].queryset,
            [source_td_1, source_td_2],
            ordered=False,
        )


class WizardSelectTableFormTests(TestCase):
    def test_names_are_source_tables(self) -> None:
        mock_db_connection = mock.Mock(
            get_table_names=mock.Mock(
                return_value=["table_1", "table_2", "table_3"]
            )
        )

        form = WizardSelectTableForm(database_connection=mock_db_connection)

        self.assertEqual(
            form.fields["table_name"].choices,
            [
                ("table_1", "table_1"),
                ("table_2", "table_2"),
                ("table_3", "table_3"),
            ],
        )


class WizardSelectFormTests(TestCase):
    def test_names_are_source_tables(self) -> None:
        mock_get_column_names = mock.Mock(
            return_value=["column_1", "column_2", "column_3"]
        )
        mock_db_connection = mock.Mock(
            get_column_names_for_table=mock_get_column_names
        )
        form = WizardSelectColumnForm(
            database_connection=mock_db_connection, table_name="test_table"
        )

        self.assertEqual(
            form.fields["column_name"].choices,
            [
                ("column_1", "column_1"),
                ("column_2", "column_2"),
                ("column_3", "column_3"),
            ],
        )
        mock_get_column_names.assert_called_once_with("test_table")
