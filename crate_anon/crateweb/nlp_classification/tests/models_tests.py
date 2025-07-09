import re
from unittest import mock

from django.test import TestCase

from crate_anon.crateweb.core.constants import (
    DJANGO_DEFAULT_CONNECTION,
)
from crate_anon.crateweb.nlp_classification.models import (
    Choice,
    Question,
    Task,
)
from crate_anon.crateweb.nlp_classification.tests.factories import (
    ColumnFactory,
    ResultFactory,
    SampleFactory,
    TableDefinitionFactory,
)
from crate_anon.nlp_manager.constants import (
    FN_SRCFIELD,
    FN_SRCPKFIELD,
    FN_SRCPKVAL,
    FN_SRCTABLE,
)
from crate_anon.nlp_manager.regex_parser import (
    FN_CONTENT,
    FN_END,
    FN_START,
)


class TaskTests(TestCase):
    databases = {DJANGO_DEFAULT_CONNECTION}

    def test_str_is_name(self) -> None:
        task = Task(name="Test")
        self.assertEqual(str(task), "Test")


class QuestionTests(TestCase):
    databases = {DJANGO_DEFAULT_CONNECTION}

    def test_str_is_title(self) -> None:
        question = Question(title="Test")
        self.assertEqual(str(question), "Test")


class ChoiceTests(TestCase):
    databases = {DJANGO_DEFAULT_CONNECTION}

    def test_str_is_description(self) -> None:
        choice = Choice(description="Test")
        self.assertEqual(str(choice), "Test")


class SampleTests(TestCase):
    databases = {DJANGO_DEFAULT_CONNECTION}

    def test_str_shows_sample_source(self) -> None:
        table_definition = TableDefinitionFactory(
            table_name="note",
            pk_column_name="id",
            db_connection_name="test",
        )
        column = ColumnFactory(table_definition=table_definition, name="note")
        sample = SampleFactory(
            source_column=column, search_term="CRP", size=100, seed=12345
        )
        self.assertEqual(
            str(sample),
            (
                "100 records from 'test.note.note' "
                "with seed 12345 and search term 'CRP'"
            ),
        )


class ResultTests(TestCase):
    def test_nlp_record_fetched(self) -> None:
        nlp_table_definition = TableDefinitionFactory(
            table_name="nlp_table", pk_column_name="id"
        )
        ColumnFactory(table_definition=nlp_table_definition, name="extra")
        result = ResultFactory(
            nlp_table_definition=nlp_table_definition, nlp_pk_value="12345"
        )

        # Not realistic
        fake_result = {"fake": "result"}

        mock_fetch = mock.Mock(return_value=fake_result)
        with mock.patch.multiple(
            "crate_anon.crateweb.nlp_classification.models.DatabaseConnection",
            fetchone_as_dict=mock_fetch,
        ):
            self.assertEqual(result.nlp_record, fake_result)

            expected_column_names = [
                FN_SRCFIELD,
                FN_SRCTABLE,
                FN_SRCPKFIELD,
                FN_SRCPKVAL,
                FN_CONTENT,
                FN_START,
                FN_END,
                "extra",
            ]

            mock_fetch.assert_called_with(
                expected_column_names,
                "nlp_table",
                where="id = %s",
                params=["12345"],
            )

    def test_source_text_fetched(self) -> None:
        test_pk_value = "12345"

        source_table_definition = TableDefinitionFactory(
            table_name="source_table",
            pk_column_name="source_pk_field",
        )

        result = ResultFactory(
            source_column=ColumnFactory(
                table_definition=source_table_definition, name="source_field"
            ),
            source_pk_value=test_pk_value,
        )
        fake_source_result = {"source_field": "source text"}
        mock_fetch_from_source = mock.Mock(return_value=fake_source_result)

        source_connection = mock.Mock(fetchone_as_dict=mock_fetch_from_source)
        with mock.patch.multiple(
            result,
            get_source_database_connection=mock.Mock(
                return_value=source_connection
            ),
        ):
            self.assertEqual(result.source_text, "source text")

            expected_column_names = ["source_field"]

            mock_fetch_from_source.assert_called_with(
                expected_column_names,
                "source_table",
                where="source_pk_field = %s",
                params=[test_pk_value],
            )

    def test_str_reports_table_definition_info(self) -> None:
        test_pk_value = "12345"

        source_table_definition = TableDefinitionFactory(
            table_name="source_table",
            pk_column_name="id",
            db_connection_name="test",
        )
        source_column = ColumnFactory(table_definition=source_table_definition)

        result = ResultFactory(
            source_column=source_column,
            source_pk_value=test_pk_value,
        )

        self.assertEqual(
            str(result), f"Item test.source_table.id={test_pk_value}"
        )

    def test_source_text_before_match(self) -> None:
        result = ResultFactory()
        fake_source_text = "before match after"
        match = re.search("match", fake_source_text)

        fake_nlp_record = {FN_START: match.start()}

        with mock.patch.multiple(
            result,
            _source_text=fake_source_text,
            _nlp_record=fake_nlp_record,
        ):
            self.assertEqual(result.before, "before ")

    def test_source_text_after_match(self) -> None:
        result = ResultFactory()
        fake_source_text = "before match after"
        match = re.search("match", fake_source_text)

        fake_nlp_record = {FN_END: match.end()}

        with mock.patch.multiple(
            result,
            _source_text=fake_source_text,
            _nlp_record=fake_nlp_record,
        ):
            self.assertEqual(result.after, " after")

    def test_match_text_from_result_content(self) -> None:
        result = ResultFactory()

        fake_nlp_record = {FN_CONTENT: "match"}

        with mock.patch.multiple(
            result,
            _nlp_record=fake_nlp_record,
        ):
            self.assertEqual(result.match, "match")

    def test_extra_fields_copied_from_nlp_record(self) -> None:
        result = ResultFactory()

        # Not a complete real world example
        fake_nlp_record = {
            FN_CONTENT: "CRP was <13 mg/dl",
            "value_text": "13",
            "units": "mg/dl",
        }

        with mock.patch.multiple(
            result,
            _nlp_record=fake_nlp_record,
            _extra_nlp_column_names=["value_text", "units"],
        ):
            self.assertEqual(
                result.extra_nlp_fields, {"value_text": "13", "units": "mg/dl"}
            )
