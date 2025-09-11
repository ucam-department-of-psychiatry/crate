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
    AdminAssignmentCreateView,
    AdminAssignmentEditView,
    AdminAssignmentListView,
    AdminColumnCreateView,
    AdminColumnEditView,
    AdminColumnListView,
    AdminHomeView,
    AdminOptionCreateView,
    AdminOptionEditView,
    AdminOptionListView,
    AdminQuestionCreateView,
    AdminQuestionEditView,
    AdminQuestionListView,
    AdminTaskCreateView,
    AdminTaskEditView,
    AdminTaskListView,
    AdminSampleSpecCreateView,
    AdminSampleSpecEditView,
    AdminSampleSpecListView,
    AdminTableDefinitionCreateView,
    AdminTableDefinitionEditView,
    AdminTableDefinitionListView,
    SampleDataWizardView,
    TaskAndQuestionWizardView,
    UserAnswerView,
    UserAssignmentView,
    UserAssignmentWizardView,
    UserHomeView,
)

urlpatterns = [
    re_path(
        r"^admin/$",
        AdminHomeView.as_view(),
        name="nlp_classification_admin_home",
    ),
    re_path(
        r"^admin/assignment/$",
        AdminAssignmentListView.as_view(),
        name="nlp_classification_admin_assignment_list",
    ),
    path(
        "admin/assignment/new",
        AdminAssignmentCreateView.as_view(),
        name="nlp_classification_admin_assignment_create",
    ),
    path(
        "admin/assignment/<int:pk>",
        AdminAssignmentEditView.as_view(),
        name="nlp_classification_admin_assignment_edit",
    ),
    re_path(
        r"^admin/column/$",
        AdminColumnListView.as_view(),
        name="nlp_classification_admin_column_list",
    ),
    path(
        "admin/column/new",
        AdminColumnCreateView.as_view(),
        name="nlp_classification_admin_column_create",
    ),
    path(
        "admin/column/<int:pk>",
        AdminColumnEditView.as_view(),
        name="nlp_classification_admin_column_edit",
    ),
    re_path(
        r"^admin/option/$",
        AdminOptionListView.as_view(),
        name="nlp_classification_admin_option_list",
    ),
    path(
        "admin/option/new",
        AdminOptionCreateView.as_view(),
        name="nlp_classification_admin_option_create",
    ),
    path(
        "admin/option/<int:pk>",
        AdminOptionEditView.as_view(),
        name="nlp_classification_admin_option_edit",
    ),
    re_path(
        r"^admin/question/$",
        AdminQuestionListView.as_view(),
        name="nlp_classification_admin_question_list",
    ),
    path(
        "admin/question/new",
        AdminQuestionCreateView.as_view(),
        name="nlp_classification_admin_question_create",
    ),
    path(
        "admin/question/<int:pk>",
        AdminQuestionEditView.as_view(),
        name="nlp_classification_admin_question_edit",
    ),
    re_path(
        r"^admin/sample_spec/$",
        AdminSampleSpecListView.as_view(),
        name="nlp_classification_admin_sample_spec_list",
    ),
    path(
        "admin/sample_spec/new",
        AdminSampleSpecCreateView.as_view(),
        name="nlp_classification_admin_sample_spec_create",
    ),
    path(
        "admin/sample_spec/<int:pk>",
        AdminSampleSpecEditView.as_view(),
        name="nlp_classification_admin_sample_spec_edit",
    ),
    re_path(
        r"^admin/table_definition/$",
        AdminTableDefinitionListView.as_view(),
        name="nlp_classification_admin_table_definition_list",
    ),
    path(
        "admin/table_definition/new",
        AdminTableDefinitionCreateView.as_view(),
        name="nlp_classification_admin_table_definition_create",
    ),
    path(
        "admin/table_definition/<int:pk>",
        AdminTableDefinitionEditView.as_view(),
        name="nlp_classification_admin_table_definition_edit",
    ),
    re_path(
        r"^admin/task/$",
        AdminTaskListView.as_view(),
        name="nlp_classification_admin_task_list",
    ),
    path(
        "admin/task/new",
        AdminTaskCreateView.as_view(),
        name="nlp_classification_admin_task_create",
    ),
    path(
        "admin/task/<int:pk>",
        AdminTaskEditView.as_view(),
        name="nlp_classification_admin_task_edit",
    ),
    path(
        "admin/task_and_question_wizard",
        TaskAndQuestionWizardView.as_view(),
        name="nlp_classification_admin_task_question_wizard",
    ),
    path(
        "admin/sample_data_wizard",
        SampleDataWizardView.as_view(),
        name="nlp_classification_admin_sample_data_wizard",
    ),
    path(
        "admin/user_assignment_wizard",
        UserAssignmentWizardView.as_view(),
        name="nlp_classification_admin_user_assignment_wizard",
    ),
    re_path(
        r"^user/$", UserHomeView.as_view(), name="nlp_classification_user_home"
    ),
    path(
        "user/assignment/<int:pk>",
        UserAssignmentView.as_view(),
        name="nlp_classification_user_assignment",
    ),
    path(
        "user/answer/<int:pk>",
        UserAnswerView.as_view(),
        name="nlp_classification_user_answer",
    ),
]
