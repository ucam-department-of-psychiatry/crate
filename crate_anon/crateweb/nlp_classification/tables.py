"""
crate_anon/crateweb/nlp_classification/tables.py

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

CRATE NLP classification tables.

"""

from typing import Optional

from crate_anon.crateweb.nlp_classification.models import (
    Assignment,
    UserAnswer,
)

from django.template import loader
from django.urls import reverse

import django_tables2 as tables


class AssignmentTable(tables.Table):
    class Meta:
        model = Assignment
        exclude = ("id", "user")

    task = tables.Column()
    sample = tables.Column()
    status = tables.TemplateColumn(
        template_name="nlp_classification/user/status_column.html",
        orderable=False,
        accessor="first_unanswered",
    )

    def render_status(
        self, record: Assignment, value: Optional[UserAnswer]
    ) -> str:
        if value is None:
            return "Complete"

        Template = loader.get_template(
            "nlp_classification/user/status_column.html"
        )

        context_dict = self.context.flatten()

        context_dict.update(
            href=reverse(
                "nlp_classification_user_answer", kwargs={"pk": value.id}
            ),
            total_answers=record.useranswer_set.all().count(),
            count=record.num_answered,
        )

        return Template.render(context_dict)


class ExportAnswersTable(tables.Table):
    class Meta:
        model = UserAnswer

        sequence = (
            "task",
            "question",
            "assignment",
            "source_table_name",
            "source_column_name",
            "source_pk_column_name",
            "source_pk_value",
            "nlp_table_name",
            "nlp_pk_column_name",
            "nlp_pk_value",
            "decision",
        )
        exclude = ("id", "source_record")

    # Columns in alphabetical order, sequence defined above
    assignment = tables.Column()
    decision = tables.Column()
    nlp_pk_column_name = tables.Column(
        accessor="source_record__sample__nlp_table_definition__pk_column_name",
        verbose_name="NLP PK column name",
    )
    nlp_pk_value = tables.Column(accessor="source_record__nlp_pk_value")
    nlp_table_name = tables.Column(
        accessor="source_record__sample__nlp_table_definition__table_name",
        verbose_name="NLP table name",
    )
    question = tables.Column(accessor="assignment__question")
    source_table_name = tables.Column(
        accessor="source_record__sample__source_column__table_definition__table_name",  # noqa: E501
        verbose_name="Source table name",
    )
    source_column_name = tables.Column(
        accessor="source_record__sample__source_column__name",
        verbose_name="Source column name",
    )
    source_pk_column_name = tables.Column(
        accessor="source_record__sample__source_column__table_definition__pk_column_name",  # noqa: E501
        verbose_name="Source PK column name",
    )
    source_pk_value = tables.Column(
        accessor="source_record__source_pk_value",
        verbose_name="Source PK value",
    )
    task = tables.Column(accessor="assignment__task")
