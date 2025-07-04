import re
from unittest import mock

from django.test import TestCase

from crate_anon.crateweb.core.constants import DJANGO_DEFAULT_CONNECTION
from crate_anon.crateweb.nlp_classification.database_connection import (
    NlpDatabaseConnection,
    ResearchDatabaseConnection,
)
from crate_anon.crateweb.nlp_classification.models import (
    Option,
    Question,
    Sample,
    Task,
)
from crate_anon.crateweb.nlp_classification.tests.factories import (
    AnswerFactory,
    NlpColumnNameFactory,
    NlpResultFactory,
    NlpTableDefinitionFactory,
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


class OptionTests(TestCase):
    databases = {DJANGO_DEFAULT_CONNECTION}

    def test_str_is_description(self) -> None:
        option = Option(description="Test")
        self.assertEqual(str(option), "Test")


class SampleTests(TestCase):
    databases = {DJANGO_DEFAULT_CONNECTION}

    def test_str_is_name(self) -> None:
        sample = Sample(name="Test")
        self.assertEqual(str(sample), "Test")


class NlpResultTests(TestCase):
    def test_nlp_record_fetched(self) -> None:
        table_definition = NlpTableDefinitionFactory(
            table_name="nlp_table", pk_column_name="id"
        )
        NlpColumnNameFactory(table_definition=table_definition, name="extra")
        nlp_result = NlpResultFactory(
            table_definition=table_definition, pk_value="12345"
        )

        # Not realistic
        fake_result = {"fake": "result"}

        mock_fetch = mock.Mock(return_value=fake_result)
        with mock.patch.multiple(
            NlpDatabaseConnection,
            fetchone_as_dict=mock_fetch,
        ):
            self.assertEqual(nlp_result.nlp_record, fake_result)

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

        table_definition = NlpTableDefinitionFactory(
            table_name="nlp_table", pk_column_name="id"
        )
        NlpColumnNameFactory(table_definition=table_definition, name="extra")
        nlp_result = NlpResultFactory(
            table_definition=table_definition, pk_value=test_pk_value
        )

        # There would be more than this in the real world, but this is enough
        # for the research database query.
        fake_nlp_result = {
            FN_SRCFIELD: "source_field",
            FN_SRCTABLE: "source_table",
            FN_SRCPKFIELD: "source_pk_field",
            FN_SRCPKVAL: test_pk_value,
        }
        mock_fetch_from_nlp = mock.Mock(return_value=fake_nlp_result)

        fake_research_result = {"source_field": "source text"}
        mock_fetch_from_research = mock.Mock(return_value=fake_research_result)
        with mock.patch.multiple(
            NlpDatabaseConnection,
            fetchone_as_dict=mock_fetch_from_nlp,
        ):
            with mock.patch.multiple(
                ResearchDatabaseConnection,
                fetchone_as_dict=mock_fetch_from_research,
            ):
                self.assertEqual(nlp_result.source_text, "source text")

                expected_column_names = ["source_field"]

                mock_fetch_from_research.assert_called_with(
                    expected_column_names,
                    "source_table",
                    where="source_pk_field = %s",
                    params=[test_pk_value],
                )

    def test_str_reports_table_definition_info(self) -> None:
        test_pk_value = "12345"

        table_definition = NlpTableDefinitionFactory(
            table_name="nlp_table", pk_column_name="id"
        )
        nlp_result = NlpResultFactory(
            table_definition=table_definition, pk_value=test_pk_value
        )

        self.assertEqual(str(nlp_result), "Item id=12345 of nlp_table")


class AnswerTests(TestCase):
    def test_source_text_fetched_from_nlp_result(self) -> None:
        answer = AnswerFactory()

        with mock.patch.multiple(answer.result, _source_text="source text"):
            self.assertEqual(answer.source_text, "source text")

    def test_source_text_before_match(self) -> None:
        answer = AnswerFactory()
        fake_source_text = "before match after"
        match = re.search("match", fake_source_text)

        fake_nlp_record = {FN_START: match.start()}

        with mock.patch.multiple(
            answer.result,
            _source_text=fake_source_text,
            _nlp_record=fake_nlp_record,
        ):
            self.assertEqual(answer.before, "before ")

    def test_source_text_after_match(self) -> None:
        answer = AnswerFactory()
        fake_source_text = "before match after"
        match = re.search("match", fake_source_text)

        fake_nlp_record = {FN_END: match.end()}

        with mock.patch.multiple(
            answer.result,
            _source_text=fake_source_text,
            _nlp_record=fake_nlp_record,
        ):
            self.assertEqual(answer.after, " after")

    def test_match_text_from_nlp_result_content(self) -> None:
        answer = AnswerFactory()

        fake_nlp_record = {FN_CONTENT: "match"}

        with mock.patch.multiple(
            answer.result,
            _nlp_record=fake_nlp_record,
        ):
            self.assertEqual(answer.match, "match")

    def test_extra_fields_copied_from_nlp_record(self) -> None:
        answer = AnswerFactory()

        # Not a complete real world example
        fake_nlp_record = {
            FN_CONTENT: "CRP was <13 mg/dl",
            "value_text": "13",
            "units": "mg/dl",
        }

        with mock.patch.multiple(
            answer.result,
            _nlp_record=fake_nlp_record,
            _extra_column_names=["value_text", "units"],
        ):
            self.assertEqual(
                answer.extra_fields, {"value_text": "13", "units": "mg/dl"}
            )
