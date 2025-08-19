from typing import Any

from django.forms import ModelForm, ModelChoiceField, RadioSelect


from crate_anon.crateweb.nlp_classification.models import (
    Task,
    UserAnswer,
    Option,
    Question,
)


class QuestionForm(ModelForm):
    class Meta:
        model = Question
        fields = ["title", "task", "options"]


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
