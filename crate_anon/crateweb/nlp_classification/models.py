from typing import Any

from django.conf import settings
from django.db import models

from crate_anon.crateweb.raw_sql.database_connection import DatabaseConnection
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
    """
    Task is the overall concept, e.g. "assessing CRP accuracy for Bob's study".
    Everything else hangs off this. There may be more than one Assignment per
    task.
    """

    name = models.CharField(max_length=100)

    def __str__(self) -> Any:
        return self.name


class Option(models.Model):
    """
    Associated with one or more questions.

    Examples: "Yes", "No"

    """

    description = models.CharField(max_length=100)

    def __str__(self) -> Any:
        return self.description


class Question(models.Model):
    """
    Question is presented to the user validating the NLP records.

    Example: "Does this text show a C-reactive protein (CRP) value?"
    (has NLP identified CRP at all even if it didn't extract the right value)

    or, more specifically: "Does this text show a C-reactive protein (CRP)
    value AND that value matches the NLP output?".

    A yes/no answer makes it easier to assess precision and recall. We will
    support more than two choices, however.
    """

    title = models.CharField(max_length=100)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    options = models.ManyToManyField(Option)

    def __str__(self) -> Any:
        return self.title


class TableDefinition(models.Model):
    """
    Points to a table in a database.
    """

    db_connection_name = models.CharField(max_length=100)
    table_name = models.CharField(max_length=100)
    pk_column_name = models.CharField(max_length=100)

    def __str__(self) -> Any:
        return f"{self.db_connection_name}.{self.table_name}"


class Column(models.Model):
    """
    Points to a particular column in a table of a database.
    Needed because we don't know which columns are in the table.
    """

    table_definition = models.ForeignKey(
        TableDefinition, on_delete=models.CASCADE
    )
    name = models.CharField(max_length=100)

    def __str__(self) -> Any:
        return f"{self.table_definition}.{self.name}"


class SourceRecord(models.Model):
    """
    This is an individual entry for a source table with optional NLP record.
    """

    source_column = models.ForeignKey(Column, on_delete=models.CASCADE)
    nlp_table_definition = models.ForeignKey(
        TableDefinition,
        null=True,
        on_delete=models.SET_NULL,
        related_name="source_records",
    )
    source_pk_value = models.CharField(max_length=100)
    nlp_pk_value = models.CharField(max_length=100)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self._nlp_dict: dict[str, Any] = None
        self._source_text: str = None
        self._extra_nlp_column_names = None

    @property
    def extra_nlp_column_names(self) -> list[str]:
        if self._extra_nlp_column_names is None:
            self._extra_nlp_column_names = [
                c.name
                for c in Column.objects.filter(
                    table_definition=self.nlp_table_definition
                )
            ]

        return self._extra_nlp_column_names

    @property
    def nlp_dict(self) -> dict[str, Any]:
        if self._nlp_dict is None:
            column_names = [
                FN_SRCFIELD,
                FN_SRCTABLE,
                FN_SRCPKFIELD,
                FN_SRCPKVAL,
                FN_CONTENT,
                FN_START,
                FN_END,
            ] + self.extra_nlp_column_names

            connection = self.get_nlp_database_connection()
            self._nlp_dict = connection.fetchone_as_dict(
                column_names,
                self.nlp_table_definition.table_name,
                where=f"{self.nlp_table_definition.pk_column_name} = %s",
                params=[self.nlp_pk_value],
            )

        return self._nlp_dict

    @property
    def before(self) -> str:
        if self.nlp_dict:
            return self.source_text[: self.nlp_dict[FN_START]]

        return self.source_text

    @property
    def after(self) -> str:
        if self.nlp_dict:
            return self.source_text[self.nlp_dict[FN_END] :]

        return ""

    @property
    def match(self) -> str:
        if self.nlp_dict:
            return self.nlp_dict[FN_CONTENT]

        return ""

    @property
    def extra_nlp_fields(self) -> dict[str, Any]:
        return dict(
            (k, self.nlp_dict[k])
            for k in self.extra_nlp_column_names
            if k in self.nlp_dict
        )

    @property
    def source_text(self) -> str:
        if self._source_text is None:
            source_column_name = self.source_column.name
            source_table = self.source_column.table_definition.table_name
            source_pk_column_name = (
                self.source_column.table_definition.pk_column_name
            )

            connection = self.get_source_database_connection()

            row = connection.fetchone_as_dict(
                [source_column_name],
                source_table,
                where=f"{source_pk_column_name} = %s",
                params=[self.source_pk_value],
            )
            self._source_text = row[source_column_name]

        return self._source_text

    def get_source_database_connection(self) -> DatabaseConnection:
        return DatabaseConnection(
            self.source_column.table_definition.db_connection_name
        )

    def get_nlp_database_connection(self) -> DatabaseConnection:
        return DatabaseConnection(self.nlp_table_definition.db_connection_name)

    def __str__(self) -> Any:
        pk_column_name = self.source_column.table_definition.pk_column_name

        return (
            f"Item {self.source_column.table_definition}.{pk_column_name}="
            f"{self.source_pk_value}"
        )


class SampleSpec(models.Model):
    """
    Used to create SourceRecords across one or more source tables and
    corresponding NLP records.

    Size might be maximum. What happens if there are fewer matching records in
    the sample?
    """

    source_column = models.ForeignKey(Column, on_delete=models.CASCADE)
    nlp_table_definition = models.ForeignKey(
        TableDefinition, on_delete=models.CASCADE
    )
    search_term = models.CharField(max_length=100)
    size = models.IntegerField()
    seed = models.PositiveIntegerField()  # default MySQL range 0-2147483647

    source_records = models.ManyToManyField(SourceRecord)

    def get_source_database_connection(self) -> DatabaseConnection:
        source_table_definition = self.source_column.table_definition

        return DatabaseConnection(source_table_definition.db_connection_name)

    def get_nlp_database_connection(self) -> DatabaseConnection:
        return DatabaseConnection(self.nlp_table_definition.db_connection_name)

    def create_source_records(self) -> None:
        source_column = self.source_column

        source_connection = self.get_source_database_connection()
        source_table_definition = source_column.table_definition
        source_table_name = source_table_definition.table_name
        source_pk_column_name = source_table_definition.pk_column_name
        source_column_name = source_column.name

        nlp_pk_column_name = self.nlp_table_definition.pk_column_name
        nlp_table_name = self.nlp_table_definition.table_name
        nlp_connection = self.get_nlp_database_connection()

        where = f"{source_column_name} LIKE %s"
        params = [f"%{self.search_term}%"]

        for source_row in source_connection.fetchall(
            [source_pk_column_name], source_table_name, where, params
        ):
            nlp_dict = nlp_connection.fetchone_as_dict(
                [nlp_pk_column_name],
                nlp_table_name,
                where=f"{FN_SRCPKVAL} = %s",
                params=[source_row[0]],
            )

            nlp_pk_value = ""
            if nlp_dict:
                nlp_pk_value = nlp_dict[nlp_pk_column_name]

            source_record, created = SourceRecord.objects.get_or_create(
                source_column=self.source_column,
                nlp_table_definition=self.nlp_table_definition,
                source_pk_value=source_row[0],
                nlp_pk_value=nlp_pk_value,
            )

            self.source_records.add(source_record)

    def __str__(self) -> Any:
        return (
            f"{self.size} records from '{self.source_column}' "
            f"with seed {self.seed} and search term '{self.search_term}'"
        )


class Assignment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    sample_spec = models.ForeignKey(SampleSpec, on_delete=models.CASCADE)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE
    )

    def create_user_answers(self, question: Question) -> None:
        for source_record in self.sample_spec.source_records.all():
            UserAnswer.objects.create(
                source_record=source_record,
                question=question,
                assignment=self,
            )


class UserAnswer(models.Model):
    """
    A user's answer to a Question. Linked with SourceRecord, which has an
    optional NLP record.

    - Note that in this analogy a question can have many answers.

    """

    source_record = models.ForeignKey(SourceRecord, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    decision = models.ForeignKey(Option, null=True, on_delete=models.SET_NULL)
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE)
