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


class UserAssignmentTable(tables.Table):
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

        context = self.context
        context["href"] = reverse(
            "nlp_classification_user_answer", kwargs={"pk": value.id}
        )

        return Template.render(context.flatten())


class FieldTable(tables.Table):
    name = tables.Column()
    value = tables.Column()
