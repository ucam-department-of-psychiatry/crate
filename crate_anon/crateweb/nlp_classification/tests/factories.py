import factory

from django.conf import settings

from crate_anon.crateweb.nlp_classification.models import (
    Assignment,
    Column,
    Option,
    Question,
    Sample,
    SourceRecord,
    TableDefinition,
    Task,
    UserAnswer,
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


class SourceRecordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SourceRecord

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


class AssignmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Assignment

    task = factory.SubFactory(TaskFactory)
    sample = factory.SubFactory(SampleFactory)
    user = factory.SubFactory(UserFactory)


class QuestionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Question

    task = factory.SubFactory(TaskFactory)


class OptionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Option

    question = factory.SubFactory(QuestionFactory)


class UserAnswerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UserAnswer

    source_record = factory.SubFactory(SourceRecordFactory)
    question = factory.SubFactory(QuestionFactory)
    decision = factory.SubFactory(OptionFactory)
    assignment = factory.SubFactory(AssignmentFactory)
