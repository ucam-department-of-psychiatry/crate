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

from crate_anon.crateweb.nlp_classification.models import (
    Assignment,
    Column,
    Option,
    Question,
    SampleSpec,
    TableDefinition,
    Task,
    UserAnswer,
)

import django_tables2 as tables


class NlpClassificationTable(tables.Table):
    name = tables.Column()
    dest_table = tables.Column()
    dest_column = tables.Column()
    sample_spec = tables.Column()
    classified = tables.Column()
    precision = tables.Column()
    recall = tables.Column()


class UserAnswerTable(tables.Table):
    class Meta:
        model = UserAnswer

    user = tables.Column()
    source_record = tables.Column()
    decision = tables.Column()
    rate = tables.LinkColumn(
        "nlp_classification_user_answer", text="Rate", args=[tables.A("pk")]
    )


class UserAssignmentTable(tables.Table):
    class Meta:
        model = Assignment

    task = tables.Column()
    sample_spec = tables.Column()
    view = tables.LinkColumn(
        "nlp_classification_user_assignment",
        text="View",
        args=[tables.A("pk")],
    )


class AdminAssignmentTable(tables.Table):
    class Meta:
        model = Assignment

    task = tables.LinkColumn(
        "nlp_classification_admin_assignment_edit",
        args=[tables.A("pk")],
    )
    sample_spec = tables.LinkColumn(
        "nlp_classification_admin_assignment_edit",
        args=[tables.A("pk")],
    )
    user = tables.LinkColumn(
        "nlp_classification_admin_assignment_edit",
        args=[tables.A("pk")],
    )


class ColumnTable(tables.Table):
    class Meta:
        model = Column

    table_definition = tables.LinkColumn(
        "nlp_classification_admin_column_edit", args=[tables.A("pk")]
    )
    name = tables.LinkColumn(
        "nlp_classification_admin_column_edit", args=[tables.A("pk")]
    )


class FieldTable(tables.Table):
    name = tables.Column()
    value = tables.Column()


class OptionTable(tables.Table):
    class Meta:
        model = Option

    description = tables.LinkColumn(
        "nlp_classification_admin_option_edit", args=[tables.A("pk")]
    )


class QuestionTable(tables.Table):
    class Meta:
        model = Question

    title = tables.LinkColumn(
        "nlp_classification_admin_question_edit", args=[tables.A("pk")]
    )
    task = tables.Column()


class SampleSpecTable(tables.Table):
    class Meta:
        model = SampleSpec

    source_column = tables.LinkColumn(
        "nlp_classification_admin_sample_spec_edit", args=[tables.A("pk")]
    )
    nlp_table_definition = tables.LinkColumn(
        "nlp_classification_admin_sample_spec_edit", args=[tables.A("pk")]
    )
    search_term = tables.LinkColumn(
        "nlp_classification_admin_sample_spec_edit", args=[tables.A("pk")]
    )
    size = tables.LinkColumn(
        "nlp_classification_admin_sample_spec_edit", args=[tables.A("pk")]
    )
    seed = tables.LinkColumn(
        "nlp_classification_admin_sample_spec_edit", args=[tables.A("pk")]
    )


class TableDefinitionTable(tables.Table):
    class Meta:
        model = TableDefinition

    db_connection_name = tables.LinkColumn(
        "nlp_classification_admin_table_definition_edit", args=[tables.A("pk")]
    )
    table_name = tables.LinkColumn(
        "nlp_classification_admin_table_definition_edit", args=[tables.A("pk")]
    )
    pk_column_name = tables.LinkColumn(
        "nlp_classification_admin_table_definition_edit", args=[tables.A("pk")]
    )


class TaskTable(tables.Table):
    class Meta:
        model = Task

    name = tables.LinkColumn(
        "nlp_classification_admin_task_edit", args=[tables.A("pk")]
    )
