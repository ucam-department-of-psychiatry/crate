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

from typing import Any

from django.urls import reverse
from django.views.generic import TemplateView, UpdateView
import django_tables2 as tables

from crate_anon.crateweb.nlp_classification.forms import AnswerForm
from crate_anon.crateweb.nlp_classification.models import Answer, Job
from crate_anon.crateweb.nlp_classification.tables import (
    AnswerTable,
    FieldTable,
    JobTable,
)


class HomeView(TemplateView):
    template_name = "nlp_classification/home.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        table = self._get_table()
        tables.RequestConfig(self.request).configure(table)
        context.update(table=table)

        return context

    def _get_table(self) -> tables.Table:
        return JobTable(Job.objects.all())


class JobView(TemplateView):
    template_name = "nlp_classification/job.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        table = self._get_table()
        tables.RequestConfig(self.request).configure(table)
        context.update(table=table)

        return context

    def _get_table(self) -> tables.Table:
        job = Job.objects.get(pk=self.kwargs["pk"])

        return AnswerTable(Answer.objects.filter(job=job))


class AnswerView(UpdateView):
    model = Answer
    template_name_suffix = "update_form"
    form_class = AnswerForm

    def get_success_url(self, **kwargs) -> str:
        next_record = (
            Answer.objects.filter(answer=None)
            .exclude(pk=self.object.pk)
            .first()
        )

        if next_record is not None:
            return reverse(
                "nlp_classification_answer", kwargs={"pk": next_record.pk}
            )

        return reverse(
            "nlp_classification_job", kwargs={"pk": self.object.job.pk}
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        table = self._get_table()
        tables.RequestConfig(self.request).configure(table)

        context.update(table=table)

        return context

    def _get_table(self) -> tables.Table:
        table_data = []

        for name, value in self.object.extra_fields.items():
            table_data.append({"name": name, "value": value})

        return FieldTable(table_data)
