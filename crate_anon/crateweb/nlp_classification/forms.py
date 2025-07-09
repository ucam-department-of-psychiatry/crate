from typing import Any

from django.forms import ModelForm, ModelChoiceField, RadioSelect


from crate_anon.crateweb.nlp_classification.models import Answer, Choice


class AnswerForm(ModelForm):
    class Meta:
        model = Answer
        fields = ["choice"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.fields["choice"] = ModelChoiceField(
            queryset=Choice.objects.filter(question=self.instance.question),
            widget=RadioSelect,
        )
