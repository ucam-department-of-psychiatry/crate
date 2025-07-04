import factory

from django.conf import settings

from crate_anon.crateweb.nlp_classification.models import (
    Answer,
    Job,
    NlpColumnName,
    NlpResult,
    NlpTableDefinition,
    Option,
    Question,
    Sample,
    Task,
)


class TaskFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Task


class NlpTableDefinitionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = NlpTableDefinition


class NlpResultFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = NlpResult

    table_definition = factory.SubFactory(NlpTableDefinitionFactory)


class NlpColumnNameFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = NlpColumnName

    table_definition = factory.SubFactory(NlpTableDefinitionFactory)


class SampleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Sample

    size = factory.Faker("pyint", min_value=100, max_value=1000)


class JobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Job

    task = factory.SubFactory(TaskFactory)
    sample = factory.SubFactory(SampleFactory)


class QuestionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Question

    task = factory.SubFactory(TaskFactory)


class OptionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Option

    question = factory.SubFactory(QuestionFactory)


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = settings.AUTH_USER_MODEL


class AnswerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Answer

    result = factory.SubFactory(NlpResultFactory)
    question = factory.SubFactory(QuestionFactory)
    answer = factory.SubFactory(OptionFactory)
    job = factory.SubFactory(JobFactory)
    user = factory.SubFactory(UserFactory)
