"""
crate_anon/crateweb/nlp_classification/tests/factories.py

===============================================================================

    Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

    This file is part of CRATE.

    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

===============================================================================

**CRATE NLP classification test factories.**

"""

from typing import Any, TYPE_CHECKING

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

if TYPE_CHECKING:
    from factory.builder import Resolver


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


class QuestionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Question
        skip_postgeneration_save = True

    task = factory.SubFactory(TaskFactory)

    @factory.post_generation
    def options(
        obj: "Resolver", create: bool, extracted: list[Option], **kwargs: Any
    ) -> None:
        if create and extracted:
            obj.options.add(*extracted)


class AssignmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Assignment

    task = factory.SubFactory(TaskFactory)
    sample = factory.SubFactory(SampleFactory)
    user = factory.SubFactory(UserFactory)
    question = factory.SubFactory(QuestionFactory)


class OptionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Option


class UserAnswerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UserAnswer

    source_record = factory.SubFactory(SourceRecordFactory)
    decision = factory.SubFactory(OptionFactory)
    assignment = factory.SubFactory(AssignmentFactory)
