"""
crate_anon/crateweb/nlp_classification/views.py

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

CRATE NLP classification views.

"""

from typing import Any, Optional

from django.urls import reverse
from django.views.generic import TemplateView, UpdateView
import django_tables2 as tables

from crate_anon.crateweb.nlp_classification.forms import UserAnswerForm
from crate_anon.crateweb.nlp_classification.models import (
    Assignment,
    UserAnswer,
)
from crate_anon.crateweb.nlp_classification.tables import (
    AssignmentTable,
    FieldTable,
    UserAnswerTable,
)


class AdminHomeView(TemplateView):
    template_name = "nlp_classification/admin/home.html"


class AdminTaskListView(TemplateView):
    template_name = "nlp_classification/admin/task_list.html"


class AdminQuestionListView(TemplateView):
    template_name = "nlp_classification/admin/question_list.html"


class AdminOptionListView(TemplateView):
    template_name = "nlp_classification/admin/option_list.html"


class AdminSampleSpecListView(TemplateView):
    template_name = "nlp_classification/admin/sample_spec_list.html"


class AdminTableDefinitionListView(TemplateView):
    template_name = "nlp_classification/admin/table_definition_list.html"


class AdminAssignmentListView(TemplateView):
    template_name = "nlp_classification/admin/assignment_list.html"


class AssignmentView(TemplateView):
    template_name = "nlp_classification/user/assignment.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        table = self._get_table()
        tables.RequestConfig(self.request).configure(table)
        context.update(table=table)

        return context

    def _get_table(self) -> tables.Table:
        assignment = Assignment.objects.get(pk=self.kwargs["pk"])

        return UserAnswerTable(
            UserAnswer.objects.filter(assignment=assignment)
        )


class UserHomeView(TemplateView):
    template_name = "nlp_classification/user/home.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        table = self._get_table()
        tables.RequestConfig(self.request).configure(table)
        context.update(table=table)

        return context

    def _get_table(self) -> tables.Table:
        return AssignmentTable(Assignment.objects.all())


class UserAnswerView(UpdateView):
    model = UserAnswer
    template_name = "nlp_classification/user/useranswerupdate_form.html"
    form_class = UserAnswerForm

    def get_success_url(self, **kwargs) -> str:
        next_record = (
            UserAnswer.objects.filter(decision=None)
            .exclude(pk=self.object.pk)
            .first()
        )

        if next_record is not None:
            return reverse(
                "nlp_classification_answer", kwargs={"pk": next_record.pk}
            )

        return reverse(
            "nlp_classification_assignment",
            kwargs={"pk": self.object.assignment.pk},
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        table = self._get_table()

        if table:
            tables.RequestConfig(self.request).configure(table)

        context.update(nlp_table=table)

        return context

    def _get_table(self) -> Optional[tables.Table]:
        table_data = []

        for name, value in self.object.source_record.extra_nlp_fields.items():
            table_data.append({"name": name, "value": value})

        if table_data:
            return FieldTable(table_data)

        return None
