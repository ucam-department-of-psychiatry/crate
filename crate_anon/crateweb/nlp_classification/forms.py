from typing import Any

from django.forms import ModelForm, ModelChoiceField, RadioSelect


from crate_anon.crateweb.nlp_classification.models import (
    Assignment,
    Option,
    Question,
    SampleSpec,
    TableDefinition,
    Task,
    UserAnswer,
)


class AssignmentForm(ModelForm):
    class Meta:
        model = Assignment
        fields = ["task", "sample_spec", "user"]


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
