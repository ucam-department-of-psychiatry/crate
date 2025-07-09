from typing import Any

from django.conf import settings
from django.db import models

from crate_anon.crateweb.nlp_classification.database_connection import (
    DatabaseConnection,
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
    """
    Task is the overall concept, e.g. "assessing CRP accuracy for Bob's study".
    Everything else hangs off this. There may be more than one Job per task
    (TODO: Names a bit ambiguous here...).
    """

    name = models.CharField(max_length=100)

    def __str__(self) -> Any:
        return self.name


class Question(models.Model):
    """
    Question is presented to the user doing the validation of NLP
    results.

    Example: "Does this text show a C-reactive protein (CRP) value?"
    (has NLP identified CRP at all even if it didn't extract the right value)

    or, more specifically: "Does this text show a C-reactive protein (CRP)
    value AND that value matches the NLP output?".

    A yes/no answer makes it easier to assess precision and recall. We will
    support multiple choice, however.
    """

    title = models.CharField(max_length=100)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)

    def __str__(self) -> Any:
        return self.title


class Choice(models.Model):
    """
    Associated with one or more questions.

    Examples: "Yes", "No"

    """

    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    description = models.CharField(max_length=100)

    def __str__(self) -> Any:
        return self.description


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


class Sample(models.Model):
    """
    Used to Results across one or more source tables and corresponding NLP
    records.

    Need:

    Size might be maximum. What happens if there are fewer matching records in
    the sample?
    """

    source_column = models.ForeignKey(Column, on_delete=models.CASCADE)
    nlp_table_definition = models.ForeignKey(
        TableDefinition, on_delete=models.CASCADE
    )
    search_term = models.CharField(max_length=100)
    size = models.IntegerField()
    seed = models.PositiveIntegerField()  # default range 0-2147483647

    def __str__(self) -> Any:
        return (
            f"{self.size} records from '{self.source_column}' "
            f"with seed {self.seed} and search term '{self.search_term}'"
        )


class Result(models.Model):
    """
    This is an individual entry for a source table with optional NLP table.
    Linked one-to-one with an Answer.
    """

    source_column = models.ForeignKey(Column, on_delete=models.CASCADE)
    nlp_table_definition = models.ForeignKey(
        TableDefinition,
        null=True,
        on_delete=models.SET_NULL,
        related_name="nlp_results",
    )
    source_pk_value = models.CharField(max_length=100)
    nlp_pk_value = models.CharField(max_length=100)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self._nlp_record: dict[str, Any] = None
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
    def nlp_record(self) -> dict[str, Any]:
        if self._nlp_record is None:
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
            self._nlp_record = connection.fetchone_as_dict(
                column_names,
                self.nlp_table_definition.table_name,
                where=f"{self.nlp_table_definition.pk_column_name} = %s",
                params=[self.nlp_pk_value],
            )

        return self._nlp_record

    @property
    def before(self) -> str:
        if self.nlp_record:
            return self.source_text[: self.nlp_record[FN_START]]

        return self.source_text

    @property
    def after(self) -> str:
        if self.nlp_record:
            return self.source_text[self.nlp_record[FN_END] :]

        return ""

    @property
    def match(self) -> str:
        if self.nlp_record:
            return self.nlp_record[FN_CONTENT]

        return ""

    @property
    def extra_nlp_fields(self) -> dict[str, Any]:
        return dict(
            (k, self.nlp_record[k])
            for k in self.extra_nlp_column_names
            if k in self.nlp_record
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


class Job(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    sample = models.ForeignKey(Sample, on_delete=models.CASCADE)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE
    )

    results = models.ManyToManyField(Result)

    def create_results(self) -> None:
        source_table_definition = self.sample.source_column.table_definition
        source_connection_name = source_table_definition.db_connection_name
        source_pk_column_name = source_table_definition.pk_column_name
        source_table_name = source_table_definition.table_name
        source_connection = DatabaseConnection(source_connection_name)

        nlp_table_definition = self.sample.nlp_table_definition
        nlp_connection_name = nlp_table_definition.db_connection_name
        nlp_pk_column_name = nlp_table_definition.pk_column_name
        nlp_table_name = nlp_table_definition.table_name
        nlp_connection = DatabaseConnection(nlp_connection_name)
        for source_row in source_connection.fetchall(
            [source_pk_column_name], source_table_name
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

            result, created = Result.objects.get_or_create(
                source_column=self.sample.source_column,
                nlp_table_definition=nlp_table_definition,
                source_pk_value=source_row[0],
                nlp_pk_value=nlp_pk_value,
            )

            self.results.add(result)


class Answer(models.Model):
    """
    A user classification result. Currently linked one-to-one with Result,
    which has an optional NLP record.

    - A Question can have many Answers... Maybe Answer is a poor choice of
      name?

    - The answer is specific to the user. Users might classify differently.

    """

    result = models.ForeignKey(Result, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    choice = models.ForeignKey(Choice, null=True, on_delete=models.SET_NULL)
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
