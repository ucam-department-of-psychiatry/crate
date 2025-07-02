from django.test import TestCase

from crate_anon.crateweb.core.constants import DJANGO_DEFAULT_CONNECTION
from crate_anon.crateweb.nlp_classification.models import (
    Option,
    Question,
    Sample,
    Task,
)


class TaskTests(TestCase):
    databases = {DJANGO_DEFAULT_CONNECTION}

    def test_str_is_name(self) -> None:
        task = Task(name="Test")
        self.assertEqual(str(task), "Test")


class QuestionTests(TestCase):
    databases = {DJANGO_DEFAULT_CONNECTION}

    def test_str_is_title(self) -> None:
        question = Question(title="Test")
        self.assertEqual(str(question), "Test")


class OptionTests(TestCase):
    databases = {DJANGO_DEFAULT_CONNECTION}

    def test_str_is_description(self) -> None:
        option = Option(description="Test")
        self.assertEqual(str(option), "Test")


class SampleTests(TestCase):
    databases = {DJANGO_DEFAULT_CONNECTION}

    def test_str_is_name(self) -> None:
        sample = Sample(name="Test")
        self.assertEqual(str(sample), "Test")
