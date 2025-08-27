"""
crate_anon/crateweb/nlp_classification/tests/views_tests.py

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

Tests for CRATE NLP classification views.

"""

from typing import Any
from unittest import mock

from django.http import QueryDict
from django.test import TestCase
from django.urls import reverse
from formtools.wizard.storage import BaseStorage
from crate_anon.crateweb.nlp_classification.constants import WizardSteps as ws
from crate_anon.crateweb.nlp_classification.models import Question, Task
from crate_anon.crateweb.nlp_classification.tests.factories import (
    OptionFactory,
    QuestionFactory,
    TableDefinitionFactory,
    TaskFactory,
    UserAnswerFactory,
)
from crate_anon.crateweb.nlp_classification.views import (
    SampleDataWizardView,
    TaskAndQuestionWizardView,
    UserAnswerView,
)


class UserAnswerViewTests(TestCase):
    def test_success_url_is_next_unanswered(self) -> None:
        this_answer = UserAnswerFactory(decision=None)
        UserAnswerFactory()  # answered
        unanswered = UserAnswerFactory(decision=None)

        view = UserAnswerView()
        view.object = this_answer

        self.assertEqual(
            view.get_success_url(),
            reverse(
                "nlp_classification_user_answer", kwargs={"pk": unanswered.pk}
            ),
        )

    def test_success_url_is_assignment_list_if_all_answered(self) -> None:
        this_answer = UserAnswerFactory(decision=None)

        view = UserAnswerView()
        view.object = this_answer

        self.assertEqual(
            view.get_success_url(),
            reverse(
                "nlp_classification_user_assignment",
                kwargs={"pk": this_answer.assignment.pk},
            ),
        )


class TestStorage(BaseStorage):
    pass


class NlpClassificationWizardViewTests(TestCase):
    def setUp(self) -> None:
        super().setUp()

        self.mock_request = mock.Mock(method="POST", FILES={})
        self.mock_request.POST = QueryDict(mutable=True)
        self.storage = TestStorage("test", request=self.mock_request)
        self.storage.init_data()
        self.mock_get_storage = mock.Mock(return_value=self.storage)

        initkwargs = self.view_class.get_initkwargs()
        self.view = self.view_class(**initkwargs)
        self.view.setup(self.mock_request)
        self.view.storage = self.storage

    def post(self, step: str, post_dict: dict[str, Any]) -> None:
        with mock.patch.multiple(
            "formtools.wizard.views", get_storage=self.mock_get_storage
        ):
            self.mock_request.POST.clear()
            for key, value in post_dict.items():
                name = f"{step}-{key}"

                if isinstance(value, list):
                    self.mock_request.POST.setlist(name, value)
                else:
                    self.mock_request.POST[name] = value

                self.mock_request.POST[self.current_step_param] = step

            self.view.dispatch(self.mock_request)

    @property
    def current_step_param(self) -> str:
        prefix = self.view.get_prefix(self.mock_request)
        return f"{prefix}-current_step"

    def assert_next_step(self, expected: str) -> None:
        self.assertEqual(
            self.view.steps.current,
            expected,
            msg="Did not go to the next step. Are there form errors?",
        )

    def assert_finished(self) -> None:
        self.assertEqual(
            self.view.steps.current,
            self.first_step,
            msg="Did not complete. Are there form errors?",
        )

    @property
    def first_step(self) -> str:
        raise NotImplementedError(
            f"first_step needs to be defined in {self.__class__.__name__}"
        )


class TaskAndQuestionWizardViewTests(NlpClassificationWizardViewTests):
    view_class = TaskAndQuestionWizardView

    @property
    def first_step(self) -> str:
        return ws.SELECT_TASK

    def test_selected_task_passed_to_select_question_form(self) -> None:
        post_data = {self.current_step_param: ws.SELECT_QUESTION}
        self.mock_request.POST = post_data
        task = TaskFactory()

        self.storage.data.update(
            step_data={
                ws.SELECT_TASK: {  # previous step
                    f"{ws.SELECT_TASK}-task": [task.id],
                }
            }
        )

        kwargs = self.view.get_form_kwargs(step=ws.SELECT_QUESTION)

        self.assertEqual(kwargs.get("task"), task)

    def test_question_saved_with_existing_task(self) -> None:
        task = TaskFactory()

        # GET request would do this
        self.storage.current_step = ws.SELECT_TASK

        # Select task
        self.post(ws.SELECT_TASK, {"task": task.id})
        self.assert_next_step(ws.SELECT_QUESTION)

        # Select question
        self.post(ws.SELECT_QUESTION, {"question": ""})
        self.assert_next_step(ws.CREATE_QUESTION)

        # Create question
        self.post(ws.CREATE_QUESTION, {"title": "Test Question"})
        self.assert_next_step(ws.SELECT_OPTIONS)

        # Select options
        self.post(ws.SELECT_OPTIONS, {"options": []})
        self.assert_next_step(ws.CREATE_OPTIONS)

        # Create options
        self.post(
            ws.CREATE_OPTIONS,
            {"description_1": "", "description_2": ""},
        )
        self.assert_finished()

        self.assertTrue(
            Question.objects.filter(task=task, title="Test Question").exists()
        )

    def test_question_saved_with_new_task(self) -> None:
        # GET request would do this
        self.storage.current_step = ws.SELECT_TASK

        # Select task
        self.post(ws.SELECT_TASK, {"task": ""})
        self.assert_next_step(ws.CREATE_TASK)

        # Create task
        self.post(ws.CREATE_TASK, {"name": "Test Task"})
        # Because we can't select an existing question for a new task
        self.assert_next_step(ws.CREATE_QUESTION)

        # Create question
        self.post(ws.CREATE_QUESTION, {"title": "Test Question"})
        self.assert_next_step(ws.SELECT_OPTIONS)

        # Select options
        self.post(ws.SELECT_OPTIONS, {"options": []})
        self.assert_next_step(ws.CREATE_OPTIONS)

        # Create options
        self.post(
            ws.CREATE_OPTIONS,
            {"description_1": "", "description_2": ""},
        )
        self.assert_finished()

        task = Task.objects.get(name="Test Task")
        self.assertTrue(
            Question.objects.filter(task=task, title="Test Question").exists()
        )

    def test_existing_task_and_question_selected(self) -> None:
        question = QuestionFactory()
        task = question.task

        # GET request would do this
        self.storage.current_step = ws.SELECT_TASK

        # Select task
        self.post(ws.SELECT_TASK, {"task": task.id})
        self.assert_next_step(ws.SELECT_QUESTION)

        # Select question
        self.post(ws.SELECT_QUESTION, {"question": question.id})
        self.assert_next_step(ws.SELECT_OPTIONS)

    def test_select_options_instructions_for_existing_question(self) -> None:
        question = QuestionFactory()

        post_data = {self.current_step_param: ws.SELECT_QUESTION}
        self.mock_request.POST = post_data

        self.storage.data.update(
            step_data={
                ws.SELECT_QUESTION: {  # previous step
                    f"{ws.SELECT_QUESTION}-question": [question.id],
                }
            }
        )

        instructions = self.view.get_instructions(ws.SELECT_OPTIONS)

        self.assertIn(question.title, instructions)

    def test_select_options_instructions_for_new_question(self) -> None:
        post_data = {self.current_step_param: ws.SELECT_QUESTION}
        self.mock_request.POST = post_data

        self.storage.data.update(
            step_data={
                ws.SELECT_QUESTION: {f"{ws.SELECT_QUESTION}-question": ""},
                ws.CREATE_QUESTION: {
                    f"{ws.CREATE_QUESTION}-title": ["Test Question"],
                },
            }
        )

        instructions = self.view.get_instructions(ws.SELECT_OPTIONS)

        self.assertIn("Test Question", instructions)

    def test_existing_question_options_selected(self) -> None:
        option_1 = OptionFactory(description="Yes")
        option_2 = OptionFactory(description="No")
        option_3 = OptionFactory(description="Maybe")

        question = QuestionFactory(options=[option_1, option_2])

        post_data = {self.current_step_param: ws.SELECT_OPTIONS}
        self.mock_request.POST = post_data

        self.storage.data.update(
            step_data={  # Earlier steps
                ws.SELECT_TASK: {
                    f"{ws.SELECT_TASK}-task": [question.task.id],
                },
                ws.SELECT_QUESTION: {
                    f"{ws.SELECT_QUESTION}-question": [question.id],
                },
            }
        )

        initial = self.view.get_form_initial(step=ws.SELECT_OPTIONS)
        options = initial.get("options")

        self.assertIn(option_1.id, options)
        self.assertIn(option_2.id, options)
        self.assertNotIn(option_3.id, options)

    def test_existing_option_added_to_existing_question(self) -> None:
        option_1 = OptionFactory(description="Yes")
        option_2 = OptionFactory(description="No")
        option_3 = OptionFactory(description="Maybe")

        question = QuestionFactory(options=[option_1, option_2])

        # GET request would do this
        self.storage.current_step = ws.SELECT_TASK

        # Select task
        self.post(ws.SELECT_TASK, {"task": question.task.id})
        self.assert_next_step(ws.SELECT_QUESTION)

        # Select question
        self.post(ws.SELECT_QUESTION, {"question": question.id})
        self.assert_next_step(ws.SELECT_OPTIONS)

        # Select options
        self.post(
            ws.SELECT_OPTIONS,
            {"options": [option_1.id, option_2.id, option_3.id]},
        )
        self.assert_next_step(ws.CREATE_OPTIONS)

        # Create options
        self.post(
            ws.CREATE_OPTIONS,
            {"description_1": "", "description_2": ""},
        )
        self.assert_finished()

        options = question.options.all()

        self.assertIn(option_1, options)
        self.assertIn(option_2, options)
        self.assertIn(option_3, options)

    def test_existing_options_removed_from_question(self) -> None:
        option_1 = OptionFactory(description="Yes")
        option_2 = OptionFactory(description="No")

        question = QuestionFactory(options=[option_1, option_2])

        # GET request would do this
        self.storage.current_step = ws.SELECT_TASK

        # Select task
        self.post(ws.SELECT_TASK, {"task": question.task.id})
        self.assert_next_step(ws.SELECT_QUESTION)

        # Select question
        self.post(ws.SELECT_QUESTION, {"question": question.id})
        self.assert_next_step(ws.SELECT_OPTIONS)

        # Select options
        self.post(ws.SELECT_OPTIONS, {"options": []})
        self.assert_next_step(ws.CREATE_OPTIONS)

        # Create options
        self.post(
            ws.CREATE_OPTIONS,
            {"description_1": "", "description_2": ""},
        )
        self.assert_finished()

        options = list(question.options.all())
        self.assertEqual(options, [])

    def test_existing_options_added_to_new_question(self) -> None:
        task = TaskFactory()

        option_1 = OptionFactory(description="Yes")
        option_2 = OptionFactory(description="No")
        option_3 = OptionFactory(description="Maybe")

        # GET request would do this
        self.storage.current_step = ws.SELECT_TASK

        # Select task
        self.post(ws.SELECT_TASK, {"task": task.id})
        self.assert_next_step(ws.SELECT_QUESTION)

        # Select question
        self.post(ws.SELECT_QUESTION, {"question": ""})
        self.assert_next_step(ws.CREATE_QUESTION)

        # Create question
        self.post(ws.CREATE_QUESTION, {"title": "Test Question"})
        self.assert_next_step(ws.SELECT_OPTIONS)

        # Select options
        self.post(
            ws.SELECT_OPTIONS,
            {"options": [option_1.id, option_2.id]},
        )
        self.assert_next_step(ws.CREATE_OPTIONS)

        # Create options
        self.post(
            ws.CREATE_OPTIONS,
            {"description_1": "", "description_2": ""},
        )
        self.assert_finished()

        question = Question.objects.get(task=task, title="Test Question")
        options = question.options.all()

        self.assertIn(option_1, options)
        self.assertIn(option_2, options)
        self.assertNotIn(option_3, options)

    def test_new_options_added_to_existing_question(self) -> None:
        question = QuestionFactory()

        # GET request would do this
        self.storage.current_step = ws.SELECT_TASK

        # Select task
        self.post(ws.SELECT_TASK, {"task": question.task.id})
        self.assert_next_step(ws.SELECT_QUESTION)

        # Select question
        self.post(ws.SELECT_QUESTION, {"question": question.id})
        self.assert_next_step(ws.SELECT_OPTIONS)

        # Select options
        self.post(ws.SELECT_OPTIONS, {"options": []})
        self.assert_next_step(ws.CREATE_OPTIONS)

        # Create options
        self.post(
            ws.CREATE_OPTIONS, {"description_1": "Yes", "description_2": "No"}
        )
        self.assert_finished()

        descriptions = [o.description for o in list(question.options.all())]

        self.assertIn("Yes", descriptions)
        self.assertIn("No", descriptions)

    def test_create_options_instructions_for_existing_question(self) -> None:
        question = QuestionFactory()

        post_data = {self.current_step_param: ws.SELECT_QUESTION}
        self.mock_request.POST = post_data

        self.storage.data.update(
            step_data={
                ws.SELECT_QUESTION: {  # previous step
                    f"{ws.SELECT_QUESTION}-question": [question.id],
                }
            }
        )

        instructions = self.view.get_instructions(ws.CREATE_OPTIONS)

        self.assertIn(question.title, instructions)


class SampleDataWizardViewTests(NlpClassificationWizardViewTests):
    view_class = SampleDataWizardView

    @property
    def first_step(self) -> str:
        return ws.SELECT_SOURCE_TABLE_DEFINITION

    def test_existing_table_definition_selected_for_source(self) -> None:
        table_definition = TableDefinitionFactory()

        # GET request would do this
        self.storage.current_step = ws.SELECT_SOURCE_TABLE_DEFINITION

        # Select table definition
        self.post(
            ws.SELECT_SOURCE_TABLE_DEFINITION,
            {"table_definition": table_definition.id},
        )
        self.assert_finished()
