from typing import Any

from django.conf import settings
from django.db import connections, models
from django.db.backends.utils import CursorWrapper

from crate_anon.crateweb.core.constants import (
    NLP_DB_CONNECTION_NAME,
    RESEARCH_DB_CONNECTION_NAME,
)
from crate_anon.nlp_manager.constants import (
    FN_SRCFIELD,
    FN_SRCPKFIELD,
    FN_SRCPKVAL,
    FN_SRCTABLE,
)

from crate_anon.nlp_manager.regex_parser import (
    FN_CONTENT,
    FN_END,
    FN_START,
)


class Task(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self) -> Any:
        return self.name


class Question(models.Model):
    title = models.CharField(max_length=100)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)

    def __str__(self) -> Any:
        return self.title


class Option(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    description = models.CharField(max_length=100)

    def __str__(self) -> Any:
        return self.description


class Sample(models.Model):
    name = models.CharField(max_length=100)
    size = models.IntegerField()

    def __str__(self) -> Any:
        return self.name


class NlpTableDefinition(models.Model):
    table_name = models.CharField(max_length=100)
    pk_column_name = models.CharField(max_length=100)


class NlpColumnName(models.Model):
    table_definition = models.ForeignKey(
        NlpTableDefinition, on_delete=models.CASCADE
    )
    name = models.CharField(max_length=100)


class NlpResult(models.Model):
    table_definition = models.ForeignKey(
        NlpTableDefinition, on_delete=models.CASCADE
    )
    pk_value = models.CharField(max_length=100)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self._nlp_record: dict[str, Any] = None
        self._source_record: dict[str, Any] = None
        self._extra_column_names = None

    @property
    def extra_column_names(self) -> list[str]:
        if self._extra_column_names is None:
            self._extra_column_names = [
                c.name
                for c in NlpColumnName.objects.filter(
                    table_definition=self.table_definition
                )
            ]

        return self._extra_column_names

    @property
    def nlp_record(self) -> CursorWrapper:
        if self._nlp_record is None:
            with connections[NLP_DB_CONNECTION_NAME].cursor() as cursor:
                column_names = [
                    FN_SRCFIELD,
                    FN_SRCTABLE,
                    FN_SRCPKFIELD,
                    FN_SRCPKVAL,
                    FN_CONTENT,
                    FN_START,
                    FN_END,
                ] + self.extra_column_names

                column_names_str = ", ".join(column_names)

                cursor.execute(
                    (
                        f"SELECT {column_names_str} "
                        f"FROM {self.table_definition.table_name} WHERE "
                        f"{self.table_definition.pk_column_name} = %s"
                    ),
                    [
                        self.pk_value,
                    ],
                )
                row = cursor.fetchone()
                self._nlp_record = {}
                for index, column_name in enumerate(column_names):
                    self._nlp_record[column_name] = row[index]

        return self._nlp_record

    @property
    def source_record(self) -> CursorWrapper:
        if self._source_record is None:
            with connections[RESEARCH_DB_CONNECTION_NAME].cursor() as cursor:
                srcfield = self.nlp_record[FN_SRCFIELD]
                srctable = self.nlp_record[FN_SRCTABLE]
                srcpkfield = self.nlp_record[FN_SRCPKFIELD]

                cursor.execute(
                    (
                        f"SELECT {srcfield} FROM {srctable} "
                        f"WHERE {srcpkfield} = %s"
                    ),
                    [
                        self.nlp_record[FN_SRCPKVAL],
                    ],
                )

                row = cursor.fetchone()
                self._source_record = dict(text=row[0])

        return self._source_record

    def __str__(self) -> Any:
        return (
            f"Item {self.table_definition.pk_column_name}={self.pk_value} "
            f"of {self.table_definition.table_name}"
        )


class Job(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    sample = models.ForeignKey(Sample, on_delete=models.CASCADE)


class Answer(models.Model):
    result = models.OneToOneField(
        NlpResult, on_delete=models.CASCADE, primary_key=True
    )
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer = models.ForeignKey(Option, null=True, on_delete=models.SET_NULL)
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE
    )

    @property
    def source_text(self) -> str:
        return self.result.source_record["text"]

    @property
    def before(self) -> str:
        return self.source_text[: self.result.nlp_record[FN_START]]

    @property
    def after(self) -> str:
        return self.source_text[self.result.nlp_record[FN_END] :]

    @property
    def match(self) -> str:
        return self.result.nlp_record[FN_CONTENT]

    @property
    def extra_fields(self) -> dict[str, Any]:
        return dict(
            (k, self.result.nlp_record[k])
            for k in self.result.extra_column_names
        )
