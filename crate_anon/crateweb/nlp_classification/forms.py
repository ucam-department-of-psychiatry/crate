from typing import Any

from django.forms import ModelForm, ModelChoiceField, RadioSelect


from crate_anon.crateweb.nlp_classification.models import (
    RatingAnswer,
    RatingOption,
)


class RatingAnswerForm(ModelForm):
    class Meta:
        model = RatingAnswer
        fields = ["answer"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.fields["answer"] = ModelChoiceField(
            queryset=RatingOption.objects.filter(
                question=self.instance.question
            ),
            widget=RadioSelect,
        )
