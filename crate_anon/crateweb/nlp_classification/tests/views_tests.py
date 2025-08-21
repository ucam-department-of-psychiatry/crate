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

from unittest import mock

from django.test import TestCase
from django.urls import reverse
from formtools.wizard.storage import BaseStorage
from crate_anon.crateweb.nlp_classification.constants import WizardSteps as ws
from crate_anon.crateweb.nlp_classification.tests.factories import (
    TaskFactory,
    UserAnswerFactory,
)
from crate_anon.crateweb.nlp_classification.views import (
    ClassificationWizardView,
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


class ClassificationWizardViewTests(TestCase):
    def setUp(self) -> None:
        super().setUp()

        self.mock_request = mock.Mock(method="POST")
        self.storage = TestStorage("test", request=self.mock_request)
        self.storage.init_data()

        initkwargs = ClassificationWizardView.get_initkwargs()
        self.view = ClassificationWizardView(**initkwargs)
        self.view.setup(self.mock_request)
        self.view.storage = self.storage

    def test_selected_task_passed_to_select_question_form(self) -> None:
        post_data = {
            "classification_wizard_view-current_step": ws.SELECT_QUESTION,
        }
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

    def test_selected_task_passed_to_create_question_form(self) -> None:
        post_data = {
            "classification_wizard_view-current_step": ws.SELECT_QUESTION,
        }
        self.mock_request.POST = post_data
        task = TaskFactory()

        self.storage.data.update(
            step_data={
                ws.SELECT_TASK: {  # earlier step
                    f"{ws.SELECT_TASK}-task": [task.id],
                }
            }
        )

        initial = self.view.get_form_initial(ws.CREATE_QUESTION)

        self.assertEqual(initial.get("task"), task)

    def test_forms_saved(self) -> None:
        form_dict = {}
        for step in [
            ws.SELECT_TASK,
            ws.CREATE_TASK,
            ws.SELECT_QUESTION,
            ws.CREATE_QUESTION,
        ]:
            mock_form = mock.Mock(save=mock.Mock())
            form_dict[step] = mock_form

        form_list = []  # not used
        self.view.done(form_list, form_dict)

        form_dict[ws.CREATE_TASK].save.assert_called()
        form_dict[ws.CREATE_QUESTION].save.assert_called()

        form_dict[ws.SELECT_TASK].save.assert_not_called()
        form_dict[ws.SELECT_QUESTION].save.assert_not_called()
