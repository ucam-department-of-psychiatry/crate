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

import random
from typing import Any, Optional

from django.contrib.auth import get_user_model
from django.http.response import HttpResponse, HttpResponseRedirect
from django.forms import Form
from django.urls import reverse
from django.views.generic import TemplateView, UpdateView
import django_tables2 as tables
from formtools.wizard.views import SessionWizardView

from crate_anon.crateweb.core.constants import (
    NLP_DB_CONNECTION_NAME,
    RESEARCH_DB_CONNECTION_NAME,
)
from crate_anon.crateweb.nlp_classification.constants import WizardSteps as ws
from crate_anon.crateweb.nlp_classification.forms import (
    UserAnswerForm,
    WizardCreateOptionsForm,
    WizardCreateQuestionForm,
    WizardCreateTaskForm,
    WizardEnterSampleSizeForm,
    WizardEnterSearchTermForm,
    WizardSelectColumnForm,
    WizardSelectMultipleColumnsForm,
    WizardSelectNlpTableDefinitionForm,
    WizardSelectOptionsForm,
    WizardSelectQuestionForm,
    WizardSelectRequiredQuestionForm,
    WizardSelectRequiredTaskForm,
    WizardSelectSampleForm,
    WizardSelectSourceTableDefinitionForm,
    WizardSelectTableForm,
    WizardSelectTaskForm,
    WizardSelectUserForm,
)
from crate_anon.crateweb.nlp_classification.models import (
    Assignment,
    Column,
    Option,
    Question,
    Sample,
    TableDefinition,
    Task,
    UserAnswer,
)
from crate_anon.crateweb.nlp_classification.tables import (
    FieldTable,
    UserAnswerTable,
    UserAssignmentTable,
)
from crate_anon.crateweb.raw_sql.database_connection import DatabaseConnection

User = get_user_model()


class AdminHomeView(TemplateView):
    template_name = "nlp_classification/admin/home.html"


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


class NlpClassificationWizardView(SessionWizardView):
    template_name = "nlp_classification/admin/wizard_form.html"

    def get_context_data(self, form: Form, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(form=form, **kwargs)
        context["instructions"] = self.get_instructions(self.steps.current)

        return context

    def get_instructions(self, step: str) -> Optional[str]:
        raise NotImplementedError(
            "get_instructions() needs to be defined in "
            f"{self.__class__.__name__}"
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


class TaskAndQuestionWizardView(NlpClassificationWizardView):
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
        (ws.CREATE_OPTIONS, WizardCreateOptionsForm),
    ]

    def get_instructions(self, step: str) -> Optional[str]:
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

        if step == ws.CREATE_OPTIONS:
            return self._get_create_options_instructions()

    def _get_select_options_instructions(self) -> str:
        return (
            f"Select options for the question '{self.question_title}'. "
            "You can create new options in the next step."
        )

    def _get_create_options_instructions(self) -> str:
        return f"Create options for the question '{self.question_title}'."

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
    def question_title(self) -> str:
        question = self.selected_question
        if question is not None:
            return question.title

        return self.created_question_title

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

        create_options_form = form_dict[ws.CREATE_OPTIONS]
        for name in ["description_1", "description_2"]:
            if description := create_options_form.cleaned_data[name]:
                option = Option.objects.create(description=description)
                question.options.add(option)

        return HttpResponseRedirect(reverse("nlp_classification_admin_home"))


def should_select_source_table(wizard: SessionWizardView) -> bool:
    return not wizard.has_selected_source_table_definition


def should_select_source_pk_column(wizard: SessionWizardView) -> bool:
    return not wizard.has_selected_source_table_definition


def should_select_nlp_table(wizard: SessionWizardView) -> bool:
    return not wizard.has_selected_nlp_table_definition


def should_select_nlp_pk_column(wizard: SessionWizardView) -> bool:
    return not wizard.has_selected_nlp_table_definition


class SampleDataWizardView(NlpClassificationWizardView):
    condition_dict = {
        ws.SELECT_SOURCE_TABLE: should_select_source_table,
        ws.SELECT_SOURCE_PK_COLUMN: should_select_source_pk_column,
        ws.SELECT_NLP_TABLE: should_select_nlp_table,
        ws.SELECT_NLP_PK_COLUMN: should_select_nlp_pk_column,
    }
    form_list = [
        (
            ws.SELECT_SOURCE_TABLE_DEFINITION,
            WizardSelectSourceTableDefinitionForm,
        ),
        (ws.SELECT_SOURCE_TABLE, WizardSelectTableForm),
        (ws.SELECT_SOURCE_PK_COLUMN, WizardSelectColumnForm),
        (ws.SELECT_SOURCE_COLUMN, WizardSelectColumnForm),
        (
            ws.SELECT_NLP_TABLE_DEFINITION,
            WizardSelectNlpTableDefinitionForm,
        ),
        (ws.SELECT_NLP_TABLE, WizardSelectTableForm),
        (ws.SELECT_NLP_PK_COLUMN, WizardSelectColumnForm),
        (ws.SELECT_NLP_COLUMNS, WizardSelectMultipleColumnsForm),
        (ws.ENTER_SAMPLE_SIZE, WizardEnterSampleSizeForm),
        (ws.ENTER_SEARCH_TERM, WizardEnterSearchTermForm),
    ]

    def get_instructions(self, step: str) -> Optional[str]:
        if step == ws.SELECT_SOURCE_TABLE_DEFINITION:
            return (
                "Select an existing source table definition or "
                "create a new one"
            )

        if step == ws.SELECT_SOURCE_TABLE:
            return "Select the table from the source database"

        if step == ws.SELECT_SOURCE_PK_COLUMN:
            return self._get_select_source_pk_column_instructions()

        if step == ws.SELECT_SOURCE_COLUMN:
            return self._get_select_source_column_instructions()

        if step == ws.SELECT_NLP_TABLE_DEFINITION:
            return (
                "Select an existing NLP table definition or "
                "create a new one"
            )

        if step == ws.SELECT_NLP_TABLE:
            return "Select the table from the NLP database"

        if step == ws.SELECT_NLP_PK_COLUMN:
            return self._get_select_nlp_pk_column_instructions()

        if step == ws.SELECT_NLP_COLUMNS:
            return self._get_select_nlp_columns_instructions()

        if step == ws.ENTER_SAMPLE_SIZE:
            return "Enter the size of the sample to be classified"

        if step == ws.ENTER_SEARCH_TERM:
            return "Enter the search term to match records to be sampled"

    def _get_select_source_pk_column_instructions(self) -> str:
        source_table_name = self.source_table_name

        return (
            "Select the primary key or other unique column for the table "
            f"'{source_table_name}'"
        )

    def _get_select_source_column_instructions(self) -> str:
        source_table_name = self.source_table_name

        return (
            f"Select the free text column for the table '{source_table_name}'"
        )

    def _get_select_nlp_pk_column_instructions(self) -> str:
        nlp_table_name = self.nlp_table_name

        return (
            "Select the primary key or other unique column for the table "
            f"'{nlp_table_name}'"
        )

    def _get_select_nlp_columns_instructions(self) -> str:
        nlp_table_name = self.nlp_table_name

        return (
            "Select any additional columns to be displayed when classifying "
            f"results from the table '{nlp_table_name}'"
        )

    def get_form_initial(self, step: str) -> dict[str, Any]:
        initial = super().get_form_initial(step)

        if step == ws.SELECT_NLP_COLUMNS:
            nlp_table_definition = self.selected_nlp_table_definition
            if nlp_table_definition is not None:
                initial["column_names"] = [
                    c.name for c in nlp_table_definition.column_set.all()
                ]

        return initial

    def get_form_kwargs(self, step=None) -> Any:
        kwargs = super().get_form_kwargs(step)
        if step in [
            ws.SELECT_SOURCE_TABLE,
            ws.SELECT_SOURCE_PK_COLUMN,
            ws.SELECT_SOURCE_COLUMN,
        ]:
            kwargs["database_connection"] = (
                self.get_source_database_connection()
            )

        if step in [ws.SELECT_SOURCE_PK_COLUMN, ws.SELECT_SOURCE_COLUMN]:
            kwargs["table_name"] = self.source_table_name

        if step in [
            ws.SELECT_NLP_TABLE,
            ws.SELECT_NLP_PK_COLUMN,
            ws.SELECT_NLP_COLUMNS,
        ]:
            kwargs["database_connection"] = self.get_nlp_database_connection()

        if step in [ws.SELECT_NLP_PK_COLUMN, ws.SELECT_NLP_COLUMNS]:
            kwargs["table_name"] = self.nlp_table_name

        return kwargs

    def get_source_database_connection(self) -> DatabaseConnection:
        return DatabaseConnection(RESEARCH_DB_CONNECTION_NAME)

    def get_nlp_database_connection(self) -> DatabaseConnection:
        return DatabaseConnection(NLP_DB_CONNECTION_NAME)

    @property
    def has_selected_source_table_definition(self) -> bool:
        return self.selected_source_table_definition is not None

    @property
    def has_selected_nlp_table_definition(self) -> bool:
        return self.selected_nlp_table_definition is not None

    @property
    def selected_source_table_definition(self) -> Optional[TableDefinition]:
        cleaned_data = (
            self.get_cleaned_data_for_step(ws.SELECT_SOURCE_TABLE_DEFINITION)
            or {}
        )

        return cleaned_data.get("table_definition")

    @property
    def source_table_name(self) -> str:
        table_name = self.selected_source_table_name
        if table_name is None:
            table_definition = self.selected_source_table_definition
            table_name = table_definition.table_name

        return table_name

    @property
    def selected_source_table_name(self) -> Optional[str]:
        cleaned_data = (
            self.get_cleaned_data_for_step(ws.SELECT_SOURCE_TABLE) or {}
        )

        return cleaned_data.get("table_name")

    @property
    def selected_source_pk_column_name(self) -> Optional[str]:
        cleaned_data = (
            self.get_cleaned_data_for_step(ws.SELECT_SOURCE_PK_COLUMN) or {}
        )

        return cleaned_data.get("column_name")

    @property
    def selected_source_column_name(self) -> str:
        cleaned_data = (
            self.get_cleaned_data_for_step(ws.SELECT_SOURCE_COLUMN) or {}
        )

        return cleaned_data.get("column_name")

    @property
    def nlp_table_name(self) -> str:
        table_name = self.selected_nlp_table_name
        if table_name is None:
            table_definition = self.selected_nlp_table_definition
            table_name = table_definition.table_name

        return table_name

    @property
    def selected_nlp_table_definition(self) -> Optional[TableDefinition]:
        cleaned_data = (
            self.get_cleaned_data_for_step(ws.SELECT_NLP_TABLE_DEFINITION)
            or {}
        )

        return cleaned_data.get("table_definition")

    @property
    def selected_nlp_table_name(self) -> Optional[str]:
        cleaned_data = (
            self.get_cleaned_data_for_step(ws.SELECT_NLP_TABLE) or {}
        )

        return cleaned_data.get("table_name")

    @property
    def selected_nlp_pk_column_name(self) -> Optional[str]:
        cleaned_data = (
            self.get_cleaned_data_for_step(ws.SELECT_NLP_PK_COLUMN) or {}
        )

        return cleaned_data.get("column_name")

    @property
    def selected_nlp_column_names(self) -> list[str]:
        cleaned_data = (
            self.get_cleaned_data_for_step(ws.SELECT_NLP_COLUMNS) or {}
        )

        return cleaned_data.get("column_names") or []

    @property
    def entered_size(self) -> int:
        cleaned_data = self.get_cleaned_data_for_step(ws.ENTER_SAMPLE_SIZE)

        return cleaned_data["size"]

    @property
    def entered_search_term(self) -> str:
        cleaned_data = self.get_cleaned_data_for_step(ws.ENTER_SEARCH_TERM)

        return cleaned_data["search_term"]

    def get_or_create_source_table_definition(self) -> TableDefinition:
        source_table_definition = self.selected_source_table_definition
        if source_table_definition is None:
            source_table_name = self.selected_source_table_name
            source_pk_column_name = self.selected_source_pk_column_name

            source_table_definition, _ = TableDefinition.objects.get_or_create(
                db_connection_name=RESEARCH_DB_CONNECTION_NAME,
                table_name=source_table_name,
                pk_column_name=source_pk_column_name,
            )

        return source_table_definition

    def get_or_create_nlp_table_definition(self) -> TableDefinition:
        nlp_table_definition = self.selected_nlp_table_definition

        if nlp_table_definition is None:
            nlp_table_name = self.selected_nlp_table_name
            nlp_pk_column_name = self.selected_nlp_pk_column_name

            nlp_table_definition, _ = TableDefinition.objects.get_or_create(
                db_connection_name=NLP_DB_CONNECTION_NAME,
                table_name=nlp_table_name,
                pk_column_name=nlp_pk_column_name,
            )

        return nlp_table_definition

    def done(
        self, form_list: list[Form], form_dict: dict[str, Form], **kwargs: Any
    ) -> HttpResponse:
        source_table_definition = self.get_or_create_source_table_definition()
        nlp_table_definition = self.get_or_create_nlp_table_definition()

        source_column_name = self.selected_source_column_name

        source_column, _ = Column.objects.get_or_create(
            table_definition=source_table_definition, name=source_column_name
        )

        size = self.entered_size
        search_term = self.entered_search_term

        for nlp_column_name in self.selected_nlp_column_names:
            Column.objects.get_or_create(
                table_definition=nlp_table_definition, name=nlp_column_name
            )

        Sample.objects.create(
            source_column=source_column,
            nlp_table_definition=nlp_table_definition,
            size=size,
            search_term=search_term,
            seed=random.randint(0, 2147483647),
        )

        return HttpResponseRedirect(reverse("nlp_classification_admin_home"))


class UserAssignmentWizardView(NlpClassificationWizardView):
    form_list = [
        (ws.SELECT_TASK, WizardSelectRequiredTaskForm),
        (ws.SELECT_QUESTION, WizardSelectRequiredQuestionForm),
        (ws.SELECT_SAMPLE, WizardSelectSampleForm),
        (ws.SELECT_USER, WizardSelectUserForm),
    ]

    def get_instructions(self, step: str) -> Optional[str]:
        if step == ws.SELECT_TASK:
            return "Select task"

        if step == ws.SELECT_QUESTION:
            return "Select question"

        if step == ws.SELECT_SAMPLE:
            return "Select the sample of records"

        if step == ws.SELECT_USER:
            return "Select the user"

    @property
    def selected_task(self) -> Optional[Task]:
        cleaned_data = self.get_cleaned_data_for_step(ws.SELECT_TASK) or {}

        return cleaned_data.get("task")

    @property
    def selected_question(self) -> Optional[Question]:
        cleaned_data = self.get_cleaned_data_for_step(ws.SELECT_QUESTION) or {}

        return cleaned_data.get("question")

    @property
    def selected_sample(self) -> Optional[Sample]:
        cleaned_data = self.get_cleaned_data_for_step(ws.SELECT_SAMPLE) or {}

        return cleaned_data.get("sample")

    @property
    def selected_user(self) -> Optional[User]:
        cleaned_data = self.get_cleaned_data_for_step(ws.SELECT_USER) or {}

        return cleaned_data.get("user")

    def done(
        self, form_list: list[Form], form_dict: dict[str, Form], **kwargs: Any
    ) -> HttpResponse:

        task = self.selected_task
        question = self.selected_question
        sample = self.selected_sample
        user = self.selected_user

        sample.create_source_records()

        assignment, _ = Assignment.objects.get_or_create(
            task=task,
            sample=sample,
            user=user,
            question=question,
        )

        assignment.create_user_answers()

        return HttpResponseRedirect(reverse("nlp_classification_admin_home"))
