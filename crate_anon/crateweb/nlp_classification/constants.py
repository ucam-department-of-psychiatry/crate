"""
crate_anon/crateweb/nlp_classification/constants.py

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

**Constants for CRATE NLP Classification.**

"""


class WizardSteps:
    # TaskAndQuestionWizardView
    SELECT_TASK = "select_task"
    CREATE_TASK = "create_task"
    SELECT_QUESTION = "select_question"
    CREATE_QUESTION = "create_question"
    SELECT_OPTIONS = "select_options"
    CREATE_OPTIONS = "create_options"

    # SampleDataWizardView
    SELECT_SOURCE_TABLE_DEFINITION = "select_source_table_definition"
    SELECT_SOURCE_TABLE = "select_source_table"
    SELECT_SOURCE_PK_COLUMN = "select_source_pk_column"
    SELECT_SOURCE_COLUMN = "select_source_column"
    SELECT_NLP_TABLE_DEFINITION = "select_nlp_table_definition"
    SELECT_NLP_TABLE = "select_nlp_table"
    SELECT_NLP_PK_COLUMN = "select_nlp_pk_column"
    SELECT_NLP_COLUMNS = "select_nlp_columns"
    ENTER_SAMPLE_SIZE = "enter_sample_size"
    ENTER_SEARCH_TERM = "enter_search_term"

    # UserAssignmentWizardView
    # SELECT_TASK as above
    SELECT_SAMPLE_SPEC = "select_sample_spec"
    SELECT_USER = "select_user"
