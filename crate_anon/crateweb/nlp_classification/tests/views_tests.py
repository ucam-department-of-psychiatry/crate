from django.test import TestCase
from django.urls import reverse

from crate_anon.crateweb.nlp_classification.tests.factories import (
    AnswerFactory,
)
from crate_anon.crateweb.nlp_classification.views import AnswerView


class AnswerViewTests(TestCase):
    def test_success_url_is_next_unanswered(self) -> None:
        this_answer = AnswerFactory(answer=None)
        AnswerFactory()  # answered
        unanswered = AnswerFactory(answer=None)

        view = AnswerView()
        view.object = this_answer

        self.assertEqual(
            view.get_success_url(),
            reverse("nlp_classification_answer", kwargs={"pk": unanswered.pk}),
        )

    def test_success_url_is_job_list_if_all_answered(self) -> None:
        this_answer = AnswerFactory(answer=None)

        view = AnswerView()
        view.object = this_answer

        self.assertEqual(
            view.get_success_url(),
            reverse(
                "nlp_classification_job", kwargs={"pk": this_answer.job.pk}
            ),
        )
