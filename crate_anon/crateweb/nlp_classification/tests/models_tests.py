from django.test import TestCase

from crate_anon.crateweb.core.constants import DJANGO_DEFAULT_CONNECTION
from crate_anon.crateweb.nlp_classification.models import (
    RatingOption,
    RatingQuestion,
    RatingSample,
    RatingTask,
)


class RatingTaskTests(TestCase):
    databases = {DJANGO_DEFAULT_CONNECTION}

    def test_str_is_name(self) -> None:
        task = RatingTask(name="Test")
        self.assertEqual(str(task), "Test")


class RatingQuestionTests(TestCase):
    databases = {DJANGO_DEFAULT_CONNECTION}

    def test_str_is_title(self) -> None:
        question = RatingQuestion(title="Test")
        self.assertEqual(str(question), "Test")


class RatingOptionTests(TestCase):
    databases = {DJANGO_DEFAULT_CONNECTION}

    def test_str_is_description(self) -> None:
        option = RatingOption(description="Test")
        self.assertEqual(str(option), "Test")


class RatingSampleTests(TestCase):
    databases = {DJANGO_DEFAULT_CONNECTION}

    def test_str_is_name(self) -> None:
        sample = RatingSample(name="Test")
        self.assertEqual(str(sample), "Test")
