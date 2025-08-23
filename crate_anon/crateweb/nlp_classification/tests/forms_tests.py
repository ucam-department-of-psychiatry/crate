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

from django.test import TestCase

from crate_anon.crateweb.nlp_classification.forms import (
    WizardSelectQuestionForm,
)
from crate_anon.crateweb.nlp_classification.tests.factories import (
    QuestionFactory,
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
