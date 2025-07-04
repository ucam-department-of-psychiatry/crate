import factory

from crate_anon.crateweb.nlp_classification.models import (
    NlpColumnName,
    NlpResult,
    NlpTableDefinition,
)


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
