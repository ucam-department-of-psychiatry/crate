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
    UserAnswer,
)

import django_tables2 as tables


class NlpClassificationTable(tables.Table):
    name = tables.Column()
    dest_table = tables.Column()
    dest_column = tables.Column()
    sample = tables.Column()
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
        "nlp_classification_answer", text="Rate", args=[tables.A("pk")]
    )


class AssignmentTable(tables.Table):
    class Meta:
        model = Assignment

    task = tables.Column()
    sample = tables.Column()
    view = tables.LinkColumn(
        "nlp_classification_assignment", text="View", args=[tables.A("pk")]
    )


class FieldTable(tables.Table):
    name = tables.Column()
    value = tables.Column()
