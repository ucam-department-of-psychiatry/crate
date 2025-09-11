"""
crate_anon/crateweb/nlp_classification/forms.py

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

CRATE NLP classification forms.

"""

from typing import Any

from django.contrib.auth import get_user_model
from django.forms import (
    CharField,
    ChoiceField,
    Form,
    HiddenInput,
    IntegerField,
    ModelForm,
    ModelChoiceField,
    ModelMultipleChoiceField,
    MultipleChoiceField,
    RadioSelect,
)

from crate_anon.crateweb.core.constants import (
    NLP_DB_CONNECTION_NAME,
    RESEARCH_DB_CONNECTION_NAME,
)
from crate_anon.crateweb.nlp_classification.models import (
    Assignment,
    Column,
    Option,
    Question,
    SampleSpec,
    TableDefinition,
    Task,
    UserAnswer,
)
from crate_anon.crateweb.raw_sql.database_connection import DatabaseConnection

User = get_user_model()


# Standard create/edit forms in alphabetical order
class AssignmentForm(ModelForm):
    class Meta:
        model = Assignment
        fields = ["task", "sample_spec", "user"]


class ColumnForm(ModelForm):
    class Meta:
        model = Column
        fields = ["table_definition", "name"]


class OptionForm(ModelForm):
    class Meta:
        model = Option
        fields = ["description"]


class QuestionForm(ModelForm):
    class Meta:
        model = Question
        fields = ["title", "task", "options"]


class SampleSpecForm(ModelForm):
    class Meta:
        model = SampleSpec
        fields = [
            "source_column",
            "nlp_table_definition",
            "search_term",
            "size",
            "seed",
        ]


class TableDefinitionForm(ModelForm):
    class Meta:
        model = TableDefinition
        fields = ["db_connection_name", "table_name", "pk_column_name"]

    db_connection_name = ChoiceField(
        choices=[
            (NLP_DB_CONNECTION_NAME, "Research database"),
            (RESEARCH_DB_CONNECTION_NAME, "NLP database"),
        ]
    )


class TaskForm(ModelForm):
    class Meta:
        model = Task
        fields = ["name"]


class UserAnswerForm(ModelForm):
    class Meta:
        model = UserAnswer
        fields = ["decision"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.fields["decision"] = ModelChoiceField(
            queryset=Option.objects.filter(question=self.instance.question),
            widget=RadioSelect,
        )


# TaskAndQuestionWizardView forms in order of step
class WizardSelectTaskForm(Form):
    task = ModelChoiceField(
        queryset=Task.objects.all(),
        required=False,
        empty_label="-- Create new task --",
    )


class WizardCreateTaskForm(TaskForm):
    pass


class WizardSelectQuestionForm(Form):
    question = ModelChoiceField(
        queryset=Question.objects.all(),
        required=False,
        empty_label="-- Create new question --",
    )

    def __init__(self, *args: Any, task=None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        if task is not None:
            self.fields["question"].queryset = Question.objects.filter(
                task=task
            )


class WizardCreateQuestionForm(ModelForm):
    class Meta:
        model = Question
        fields = ["title", "task"]

    task = ModelChoiceField(
        queryset=Task.objects.all(), widget=HiddenInput, required=False
    )


class WizardSelectOptionsForm(Form):
    options = ModelMultipleChoiceField(
        queryset=Option.objects.all(),
        required=False,
    )


class WizardCreateOptionsForm(Form):
    description_1 = CharField(required=False)
    description_2 = CharField(required=False)


# SampleDataWizardView forms in order of step
class WizardSelectSourceTableDefinitionForm(Form):
    table_definition = ModelChoiceField(
        queryset=TableDefinition.objects.filter(
            db_connection_name=RESEARCH_DB_CONNECTION_NAME
        ),
        required=False,
        empty_label="-- Create new source table definition --",
    )


class WizardSelectTableForm(Form):
    table_name = ChoiceField()

    def __init__(
        self,
        database_connection: DatabaseConnection,
        *args: Any,
        **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)

        table_names = database_connection.get_table_names()

        self.fields["table_name"].choices = [
            (name, name) for name in table_names
        ]


class WizardSelectColumnForm(Form):
    column_name = ChoiceField()

    def __init__(
        self,
        database_connection: DatabaseConnection,
        table_name: str,
        *args: Any,
        **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)

        column_names = database_connection.get_column_names_for_table(
            table_name,
        )

        self.fields["column_name"].choices = [
            (name, name) for name in column_names
        ]


class WizardSelectMultipleColumnsForm(Form):
    column_names = MultipleChoiceField()

    def __init__(
        self,
        database_connection: DatabaseConnection,
        table_name: str,
        *args: Any,
        **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)

        column_names = database_connection.get_column_names_for_table(
            table_name,
        )

        self.fields["column_names"].choices = [
            (name, name) for name in column_names
        ]


class WizardSelectNlpTableDefinitionForm(Form):
    table_definition = ModelChoiceField(
        queryset=TableDefinition.objects.filter(
            db_connection_name=NLP_DB_CONNECTION_NAME
        ),
        required=False,
        empty_label="-- Create new NLP table definition --",
    )


class WizardEnterSampleSizeForm(Form):
    size = IntegerField(min_value=1)


class WizardEnterSearchTermForm(Form):
    search_term = CharField(max_length=100)  # TODO set from model?


# UserAssignmentWizardView forms in order of step


class WizardSelectRequiredTaskForm(Form):
    task = ModelChoiceField(queryset=Task.objects.all(), required=True)


class WizardSelectSampleSpecForm(Form):
    sample_spec = ModelChoiceField(
        queryset=SampleSpec.objects.all(), required=True
    )


class WizardSelectUserForm(Form):
    user = ModelChoiceField(queryset=User.objects.all(), required=True)
