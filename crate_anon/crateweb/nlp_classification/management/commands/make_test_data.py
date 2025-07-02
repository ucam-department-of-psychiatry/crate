from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import connections

from crate_anon.crateweb.nlp_classification.models import (
    NlpColumnName,
    NlpResult,
    NlpTableDefinition,
    Answer,
    Job,
    Option,
    Question,
    Sample,
    Task,
)


class Command(BaseCommand):
    help = "Insert test data into the database"

    def handle(self, *args: Any, **options: Any):
        Sample.objects.all().delete()
        Task.objects.all().delete()
        NlpResult.objects.all().delete()

        sample = Sample.objects.create(name="Test sample", size=100)
        task = Task.objects.create(name="Test task")
        crp_question = Question.objects.create(
            task=task,
            title=(
                "Does this text show a C-reactive protein (CRP) value "
                "AND that value matches the NLP output?"
            ),
        )
        Option.objects.create(question=crp_question, description="Yes")
        Option.objects.create(question=crp_question, description="No")

        fruit_question = Question.objects.create(
            task=task, title="Which fruit do you prefer?"
        )
        Option.objects.create(question=fruit_question, description="Apple")
        Option.objects.create(question=fruit_question, description="Banana")
        Option.objects.create(question=fruit_question, description="Pear")

        job = Job.objects.create(task=task, sample=sample)

        get_user_model().objects.get(username="test").delete()
        user = get_user_model().objects.create(username="test")

        table_definition = NlpTableDefinition.objects.create(
            table_name="crp", pk_column_name="_pk"
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
            NlpColumnName.objects.create(
                table_definition=table_definition, name=column_name
            )

        with connections["nlp"].cursor() as cursor:
            cursor.execute("SELECT _pk FROM crp")
            for row in cursor.fetchall():
                nlp_result = NlpResult.objects.create(
                    table_definition=table_definition, pk_value=row[0]
                )
                Answer.objects.create(
                    result=nlp_result,
                    question=crp_question,
                    job=job,
                    user=user,
                )
