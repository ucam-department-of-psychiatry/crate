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
    SampleSpecForm,
    TableDefinitionForm,
    TaskForm,
    WizardCreateQuestionForm,
    WizardCreateTaskForm,
    WizardSelectOptionsForm,
    WizardSelectQuestionForm,
    WizardSelectTaskForm,
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
    return not wizard.has_selected_task


def should_select_question(wizard: SessionWizardView) -> bool:
    return wizard.has_selected_task


def should_create_question(wizard: SessionWizardView) -> bool:
    return not wizard.has_selected_question


class ClassificationWizardView(SessionWizardView):
    condition_dict = {
        ws.CREATE_TASK: should_create_task,
        ws.SELECT_QUESTION: should_select_question,
        ws.CREATE_QUESTION: should_create_question,
    }
    form_list = [
        (ws.SELECT_TASK, WizardSelectTaskForm),
        (ws.CREATE_TASK, WizardCreateTaskForm),
        (ws.SELECT_QUESTION, WizardSelectQuestionForm),
        (ws.CREATE_QUESTION, WizardCreateQuestionForm),
        (ws.SELECT_OPTIONS, WizardSelectOptionsForm),
    ]

    template_name = "nlp_classification/admin/wizard_form.html"

    def get_instructions(self, step: str) -> str:
        if step == ws.SELECT_TASK:
            return "Select an existing task or create a new task"

        if step == ws.CREATE_TASK:
            return "Enter the details for the new task"

        if step == ws.SELECT_QUESTION:
            return "Select an existing question or create a new question"

        if step == ws.CREATE_QUESTION:
            return "Enter the details for the new question"

        if step == ws.SELECT_OPTIONS:
            return self._get_select_options_instructions()

    def _get_select_options_instructions(self) -> str:
        question = self.selected_question
        if question is not None:
            title = question.title
        else:
            title = self.created_question_title

        return (
            f"Select options for the question '{title}'. "
            "You can create new options in the next step."
        )

    def get_cleaned_data_for_step(self, step: str) -> Optional[dict[str, Any]]:
        # https://github.com/jazzband/django-formtools/issues/266
        # self.get_form() can raise a KeyError if the step does not exist in
        # the dynamic form list because it has been excluded from
        # condition_dict. The documentation does not mention this.
        try:
            return super().get_cleaned_data_for_step(step)
        except KeyError:
            return None

    def get_form_initial(self, step: str) -> dict[str, Any]:
        initial = super().get_form_initial(step)

        if step == ws.SELECT_OPTIONS:
            question = self.selected_question
            if question is not None:
                initial["options"] = [o.id for o in question.options.all()]

        return initial

    def get_form_kwargs(self, step=None) -> Any:
        kwargs = super().get_form_kwargs(step)
        if step == ws.SELECT_QUESTION:
            kwargs["task"] = self.selected_task

        return kwargs

    @property
    def has_selected_task(self) -> bool:
        return self.selected_task is not None

    @property
    def selected_task(self) -> Optional[Task]:
        cleaned_data = self.get_cleaned_data_for_step(ws.SELECT_TASK) or {}

        return cleaned_data.get("task")

    @property
    def has_selected_question(self) -> bool:
        return self.selected_question is not None

    @property
    def selected_question(self) -> Optional[Question]:
        cleaned_data = self.get_cleaned_data_for_step(ws.SELECT_QUESTION) or {}

        return cleaned_data.get("question")

    @property
    def created_question_title(self) -> Optional[str]:
        cleaned_data = self.get_cleaned_data_for_step(ws.CREATE_QUESTION) or {}

        return cleaned_data.get("title")

    @property
    def selected_options(self) -> Optional[list[Option]]:
        cleaned_data = self.get_cleaned_data_for_step(ws.SELECT_OPTIONS) or {}

        options = cleaned_data.get("options")
        if options is not None:
            return list(options)

        return None

    def get_context_data(self, form: Form, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(form=form, **kwargs)

        context["instructions"] = self.get_instructions(self.steps.current)

        return context

    def done(
        self, form_list: list[Form], form_dict: dict[str, Form], **kwargs: Any
    ) -> HttpResponse:

        task = self.selected_task
        if task is None:
            create_task_form = form_dict[ws.CREATE_TASK]
            task = create_task_form.save()

        question = self.selected_question
        if question is None:
            create_question_form = form_dict[ws.CREATE_QUESTION]
            question = create_question_form.instance

            question.task = task
            question.save()

        options = self.selected_options
        if options is not None:
            question.options.set(options)

        return HttpResponseRedirect(reverse("nlp_classification_admin_home"))
