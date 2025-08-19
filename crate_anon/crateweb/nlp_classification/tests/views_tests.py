from django.test import TestCase
from django.urls import reverse

from crate_anon.crateweb.nlp_classification.tests.factories import (
    UserAnswerFactory,
)
from crate_anon.crateweb.nlp_classification.views import UserAnswerView


class UserAnswerViewTests(TestCase):
    def test_success_url_is_next_unanswered(self) -> None:
        this_answer = UserAnswerFactory(decision=None)
        UserAnswerFactory()  # answered
        unanswered = UserAnswerFactory(decision=None)

        view = UserAnswerView()
        view.object = this_answer

        self.assertEqual(
            view.get_success_url(),
            reverse(
                "nlp_classification_user_answer", kwargs={"pk": unanswered.pk}
            ),
        )

    def test_success_url_is_assignment_list_if_all_answered(self) -> None:
        this_answer = UserAnswerFactory(decision=None)

        view = UserAnswerView()
        view.object = this_answer

        self.assertEqual(
            view.get_success_url(),
            reverse(
                "nlp_classification_user_assignment",
                kwargs={"pk": this_answer.assignment.pk},
            ),
        )
