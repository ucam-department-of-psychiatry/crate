from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

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
from crate_anon.crateweb.core.constants import (
    NLP_DB_CONNECTION_NAME,
    RESEARCH_DB_CONNECTION_NAME,
)


class Command(BaseCommand):
    help = "Insert test data into the database"

    def handle(self, *args: Any, **options: Any):
        Sample.objects.all().delete()
        Task.objects.all().delete()
        SourceRecord.objects.all().delete()

        source_note = TableDefinition.objects.create(
            db_connection_name=RESEARCH_DB_CONNECTION_NAME,
            table_name="note",
            pk_column_name="note_id",
        )
        note_column = Column.objects.create(
            table_definition=source_note, name="note"
        )
        crp_table_definition = TableDefinition.objects.create(
            db_connection_name=NLP_DB_CONNECTION_NAME,
            table_name="crp",
            pk_column_name="_pk",
        )
        for column_name in [
            "variable_text",
            "relation_text",
            "relation",
            "value_text",
            "units",
            "value_mg_L",
            "tense_text",
            "tense",
        ]:
            Column.objects.create(
                table_definition=crp_table_definition, name=column_name
            )

        sample = Sample.objects.create(
            source_column=note_column,
            nlp_table_definition=crp_table_definition,
            size=100,
            search_term="",
            seed=123456,
        )

        task = Task.objects.create(name="Test task")
        crp_question = Question.objects.create(
            task=task,
            title=(
                "Does this text show a C-reactive protein (CRP) value "
                "AND that value matches the NLP output?"
            ),
        )
        yes = Option.objects.create(description="Yes")
        no = Option.objects.create(description="No")

        crp_question.options.add(yes)
        crp_question.options.add(no)

        fruit_question = Question.objects.create(
            task=task, title="Which fruit do you prefer?"
        )
        apple = Option.objects.create(description="Apple")
        banana = Option.objects.create(description="Banana")
        pear = Option.objects.create(description="Pear")

        fruit_question.options.add(apple)
        fruit_question.options.add(banana)
        fruit_question.options.add(pear)

        get_user_model().objects.get(username="test").delete()
        user = get_user_model().objects.create(username="test")

        assignment = Assignment.objects.create(
            task=task, sample=sample, user=user
        )

        assignment.assign_source_records()

        for source_record in assignment.source_records.all():
            UserAnswer.objects.create(
                source_record=source_record,
                question=crp_question,
                assignment=assignment,
            )
