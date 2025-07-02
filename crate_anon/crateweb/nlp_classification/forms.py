from typing import Any

from django.forms import ModelForm, ModelChoiceField, RadioSelect


from crate_anon.crateweb.nlp_classification.models import Answer, Option


class AnswerForm(ModelForm):
    class Meta:
        model = Answer
        fields = ["answer"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.fields["answer"] = ModelChoiceField(
            queryset=Option.objects.filter(question=self.instance.question),
            widget=RadioSelect,
        )
