import factory

from django.conf import settings

from crate_anon.crateweb.nlp_classification.models import (
    Answer,
    Choice,
    Column,
    Job,
    Question,
    Result,
    Sample,
    TableDefinition,
    Task,
)


class TaskFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Task


class TableDefinitionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TableDefinition


class ColumnFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Column

    table_definition = factory.SubFactory(TableDefinitionFactory)


class ResultFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Result

    source_column = factory.SubFactory(ColumnFactory)
    nlp_table_definition = factory.SubFactory(TableDefinitionFactory)


class SampleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Sample

    source_column = factory.SubFactory(ColumnFactory)
    nlp_table_definition = factory.SubFactory(TableDefinitionFactory)
    seed = factory.Faker("pyint", min_value=0, max_value=2147483647)
    size = factory.Faker("pyint", min_value=100, max_value=1000)


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = settings.AUTH_USER_MODEL

    username = factory.Sequence(lambda n: f"User {n+1}")


class JobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Job

    task = factory.SubFactory(TaskFactory)
    sample = factory.SubFactory(SampleFactory)
    user = factory.SubFactory(UserFactory)


class QuestionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Question

    task = factory.SubFactory(TaskFactory)


class ChoiceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Choice

    question = factory.SubFactory(QuestionFactory)


class AnswerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Answer

    result = factory.SubFactory(ResultFactory)
    question = factory.SubFactory(QuestionFactory)
    choice = factory.SubFactory(ChoiceFactory)
    job = factory.SubFactory(JobFactory)
