"""
crate_anon/crateweb/nlp_classification/views.py

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

CRATE NLP classification views.

"""

from typing import Any, Optional

from django.http.response import HttpResponse, HttpResponseRedirect
from django.forms import Form
from django.urls import reverse
from django.views.generic import CreateView, TemplateView, UpdateView
import django_tables2 as tables
from formtools.wizard.views import SessionWizardView

from crate_anon.crateweb.nlp_classification.constants import WizardSteps as ws
from crate_anon.crateweb.nlp_classification.forms import (
    AssignmentForm,
    OptionForm,
    QuestionForm,
    QuestionSelectionForm,
    QuestionWizardForm,
    SampleSpecForm,
    TableDefinitionForm,
    TaskForm,
    TaskSelectionForm,
    UserAnswerForm,
)
from crate_anon.crateweb.nlp_classification.models import (
    Assignment,
    Option,
    Question,
    SampleSpec,
    TableDefinition,
    Task,
    UserAnswer,
)
from crate_anon.crateweb.nlp_classification.tables import (
    AdminAssignmentTable,
    FieldTable,
    OptionTable,
    QuestionTable,
    SampleSpecTable,
    TableDefinitionTable,
    TaskTable,
    UserAnswerTable,
    UserAssignmentTable,
)


class AdminHomeView(TemplateView):
    template_name = "nlp_classification/admin/home.html"


class AdminTaskListView(TemplateView):
    template_name = "nlp_classification/admin/task_list.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        table = self._get_table()
        tables.RequestConfig(self.request).configure(table)
        context.update(table=table)

        return context

    def _get_table(self) -> tables.Table:
        return TaskTable(Task.objects.all())


class AdminTaskCreateView(CreateView):
    model = Task
    template_name = "nlp_classification/admin/update_form.html"
    form_class = TaskForm

    def get_success_url(self):
        return reverse("nlp_classification_admin_task_list")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(title="New task")

        return context


class AdminTaskEditView(UpdateView):
    model = Task
    template_name = "nlp_classification/admin/update_form.html"
    form_class = TaskForm

    def get_success_url(self):
        return reverse("nlp_classification_admin_task_list")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(title="Edit task")

        return context


class AdminQuestionListView(TemplateView):
    template_name = "nlp_classification/admin/question_list.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        table = self._get_table()
        tables.RequestConfig(self.request).configure(table)
        context.update(table=table)

        return context

    def _get_table(self) -> tables.Table:
        return QuestionTable(Question.objects.all())


class AdminQuestionCreateView(CreateView):
    model = Question
    template_name = "nlp_classification/admin/update_form.html"
    form_class = QuestionForm

    def get_success_url(self):
        return reverse("nlp_classification_admin_question_list")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(title="New question")

        return context


class AdminQuestionEditView(UpdateView):
    model = Question
    template_name = "nlp_classification/admin/update_form.html"
    form_class = QuestionForm

    def get_success_url(self):
        return reverse("nlp_classification_admin_question_list")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(title="Edit question")

        return context


class AdminOptionListView(TemplateView):
    template_name = "nlp_classification/admin/option_list.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        table = self._get_table()
        tables.RequestConfig(self.request).configure(table)
        context.update(table=table)

        return context

    def _get_table(self) -> tables.Table:
        return OptionTable(Option.objects.all())


class AdminOptionCreateView(CreateView):
    model = Option
    template_name = "nlp_classification/admin/update_form.html"
    form_class = OptionForm

    def get_success_url(self):
        return reverse("nlp_classification_admin_option_list")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(title="New option")

        return context


class AdminOptionEditView(UpdateView):
    model = Option
    template_name = "nlp_classification/admin/update_form.html"
    form_class = OptionForm

    def get_success_url(self):
        return reverse("nlp_classification_admin_option_list")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(title="Edit option")

        return context


class AdminSampleSpecListView(TemplateView):
    template_name = "nlp_classification/admin/sample_spec_list.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        table = self._get_table()
        tables.RequestConfig(self.request).configure(table)
        context.update(table=table)

        return context

    def _get_table(self) -> tables.Table:
        return SampleSpecTable(SampleSpec.objects.all())


class AdminSampleSpecCreateView(CreateView):
    model = SampleSpec
    template_name = "nlp_classification/admin/update_form.html"
    form_class = SampleSpecForm

    def get_success_url(self):
        return reverse("nlp_classification_admin_sample_spec_list")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(title="New sample specification")

        return context


class AdminSampleSpecEditView(UpdateView):
    model = SampleSpec
    template_name = "nlp_classification/admin/update_form.html"
    form_class = SampleSpecForm

    def get_success_url(self):
        return reverse("nlp_classification_admin_sample_spec_list")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(title="Edit sample specification")

        return context


class AdminTableDefinitionListView(TemplateView):
    template_name = "nlp_classification/admin/table_definition_list.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        table = self._get_table()
        tables.RequestConfig(self.request).configure(table)
        context.update(table=table)

        return context

    def _get_table(self) -> tables.Table:
        return TableDefinitionTable(TableDefinition.objects.all())


class AdminTableDefinitionCreateView(CreateView):
    model = TableDefinition
    template_name = "nlp_classification/admin/update_form.html"
    form_class = TableDefinitionForm

    def get_success_url(self):
        return reverse("nlp_classification_admin_table_definition_list")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(title="New table definition")

        return context


class AdminTableDefinitionEditView(UpdateView):
    model = TableDefinition
    template_name = "nlp_classification/admin/update_form.html"
    form_class = TableDefinitionForm

    def get_success_url(self):
        return reverse("nlp_classification_admin_table_definition_list")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(title="Edit table definition")

        return context


class AdminAssignmentListView(TemplateView):
    template_name = "nlp_classification/admin/assignment_list.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        table = self._get_table()
        tables.RequestConfig(self.request).configure(table)
        context.update(table=table)

        return context

    def _get_table(self) -> tables.Table:
        return AdminAssignmentTable(Assignment.objects.all())


class AdminAssignmentCreateView(CreateView):
    model = Assignment
    template_name = "nlp_classification/admin/update_form.html"
    form_class = AssignmentForm

    def get_success_url(self):
        return reverse("nlp_classification_admin_assignment_list")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(title="New assignment")

        return context


class AdminAssignmentEditView(UpdateView):
    model = Assignment
    template_name = "nlp_classification/admin/update_form.html"
    form_class = AssignmentForm

    def get_success_url(self):
        return reverse("nlp_classification_admin_assignment_list")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(title="Edit assigment")

        return context


class UserAssignmentView(TemplateView):
    template_name = "nlp_classification/user/assignment.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        table = self._get_table()
        tables.RequestConfig(self.request).configure(table)
        context.update(table=table)

        return context

    def _get_table(self) -> tables.Table:
        assignment = Assignment.objects.get(pk=self.kwargs["pk"])

        return UserAnswerTable(
            UserAnswer.objects.filter(assignment=assignment)
        )


class UserHomeView(TemplateView):
    template_name = "nlp_classification/user/home.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        table = self._get_table()
        tables.RequestConfig(self.request).configure(table)
        context.update(table=table)

        return context

    def _get_table(self) -> tables.Table:
        return UserAssignmentTable(Assignment.objects.all())


class UserAnswerView(UpdateView):
    model = UserAnswer
    template_name = "nlp_classification/user/useranswerupdate_form.html"
    form_class = UserAnswerForm

    def get_success_url(self, **kwargs) -> str:
        next_record = (
            UserAnswer.objects.filter(decision=None)
            .exclude(pk=self.object.pk)
            .first()
        )

        if next_record is not None:
            return reverse(
                "nlp_classification_user_answer", kwargs={"pk": next_record.pk}
            )

        return reverse(
            "nlp_classification_user_assignment",
            kwargs={"pk": self.object.assignment.pk},
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        table = self._get_table()

        if table:
            tables.RequestConfig(self.request).configure(table)

        context.update(nlp_table=table)

        return context

    def _get_table(self) -> Optional[tables.Table]:
        table_data = []

        for name, value in self.object.source_record.extra_nlp_fields.items():
            table_data.append({"name": name, "value": value})

        if table_data:
            return FieldTable(table_data)

        return None


def should_create_task(wizard: SessionWizardView) -> bool:
    return wizard.get_task() is None


class ClassificationWizardView(SessionWizardView):
    condition_dict = {
        ws.CREATE_TASK: should_create_task,
    }
    form_list = [
        (ws.SELECT_TASK, TaskSelectionForm),
        (ws.CREATE_TASK, TaskForm),
        (ws.SELECT_QUESTION, QuestionSelectionForm),
        (ws.CREATE_QUESTION, QuestionWizardForm),
    ]

    template_name = "nlp_classification/admin/wizard_form.html"

    instructions = {
        ws.SELECT_TASK: "Select an existing task or create a new task",
        ws.CREATE_TASK: "Enter the details for the new task",
        ws.SELECT_QUESTION: (
            "Select an existing question or create a new question"
        ),
        ws.CREATE_QUESTION: "Enter the details for the new question",
    }

    def get_form_kwargs(self, step=None) -> Any:
        kwargs = super().get_form_kwargs(step)
        if step == ws.SELECT_QUESTION:
            kwargs["task"] = self.get_task()

        return kwargs

    def get_form_initial(self, step: str) -> dict[str, Any]:
        initial = super().get_form_initial(step)

        if step == ws.CREATE_QUESTION:
            initial["task"] = self.get_task()

        return initial

    def get_task(self) -> Optional[Task]:
        cleaned_data = self.get_cleaned_data_for_step(ws.SELECT_TASK) or {}

        return cleaned_data.get("task")

    def get_context_data(self, form: Form, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(form=form, **kwargs)

        context["instructions"] = self.instructions[self.steps.current]

        return context

    def done(
        self, form_list: list[Form], form_dict: dict[str, Form], **kwargs: Any
    ) -> HttpResponse:
        for step_name, form in form_dict.items():
            if step_name in (ws.CREATE_TASK, ws.CREATE_QUESTION):
                form.save()

        return HttpResponseRedirect(reverse("nlp_classification_admin_home"))
