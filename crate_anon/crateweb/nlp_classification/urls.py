"""
crate_anon/crateweb/nlp_classification/urls.py

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

**Django URL configuration for CRATE NLP Classification.**

"""

from django.urls import path, re_path

from crate_anon.crateweb.nlp_classification.views import (
    AssignmentView,
    AdminHomeView,
    AdminTaskListView,
    AdminQuestionListView,
    AdminOptionListView,
    AdminSampleSpecListView,
    AdminTableDefinitionListView,
    AdminAssignmentListView,
    UserAnswerView,
    UserHomeView,
)

urlpatterns = [
    re_path(
        r"^admin/$",
        AdminHomeView.as_view(),
        name="nlp_classification_admin_home",
    ),
    re_path(
        r"^admin/tasks/$",
        AdminTaskListView.as_view(),
        name="nlp_classification_admin_task_list",
    ),
    re_path(
        r"^admin/questions/$",
        AdminQuestionListView.as_view(),
        name="nlp_classification_admin_question_list",
    ),
    re_path(
        r"^admin/options/$",
        AdminOptionListView.as_view(),
        name="nlp_classification_admin_option_list",
    ),
    re_path(
        r"^admin/sample_specs/$",
        AdminSampleSpecListView.as_view(),
        name="nlp_classification_admin_sample_spec_list",
    ),
    re_path(
        r"^admin/table_definitions/$",
        AdminTableDefinitionListView.as_view(),
        name="nlp_classification_admin_table_definition_list",
    ),
    re_path(
        r"^admin/assignments/$",
        AdminAssignmentListView.as_view(),
        name="nlp_classification_admin_assignment_list",
    ),
    re_path(
        r"^user/$", UserHomeView.as_view(), name="nlp_classification_user_home"
    ),
    path(
        "assignment/<int:pk>",
        AssignmentView.as_view(),
        name="nlp_classification_assignment",
    ),
    path(
        "answer/<int:pk>",
        UserAnswerView.as_view(),
        name="nlp_classification_answer",
    ),
]
