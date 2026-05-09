..  crate_anon/docs/source/website_using/nlp_classification.rst

..  Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).
    .
    This file is part of CRATE.
    .
    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    .
    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.
    .
    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

NLP Classification interface
----------------------------

Introduction
~~~~~~~~~~~~

CRATE provides a user interface for human validation of NLP results.

Using a series of form wizards, an administrator (superuser) can create samples
of anonymised free text and any associated NLP results. The administrator
assigns the samples to other users for validation, along with a question
and possible answers.

The users performing the validation see each free text record from the sample in
turn, with any NLP matches highlighted. Answering the question advances to the
next record.

The administrator can then export all of the recorded answers for analysis and
e.g. precision and recall calculations.


Example
~~~~~~~

Here is an example to describe how the system works:

Suppose you wish to validate the results of the C-reactive protein (CRP) NLP
tool. As an administrator, you log in to CRATE and select **Administration**,
under **NLP Classification** from the home page. From here, simply work down the
list of form wizards under **Quick setup**:

Task
    The Task is the overriding concept. e.g. ``Assessing CRP accuracy for Bob's study``.

Question
    The Question is presented to the user classifying the NLP records. In our
    example this could be: ``Does this text show a C-reactive protein (CRP) value AND that
    value matches the NLP output?``. There can be more than one question per task.

Option
    The available answers to the question. A yes/no answer makes it easier to calculate precision and recall. CRATE
    support more than two choices and you can re-run the form wizard to add more options.

Source table definition
    This describes the table from where the anonymised records are to be sampled,
    e.g. column ``text`` of ``clinical_documents``. You will also need to provide a
    primary key or other unique column for this table.

NLP table definition
    This describes the table from where the associated NLP records are to be
    fetched, e.g. ``crp``. You will also need to provide a primary key or other
    unique column for this table. Optionally you can select any additional
    columns from this table to be displayed to the user alongside the anonymised
    text, which would assist the user in validating the NLP. In our example
    these could be ``relation``, ``tense``, ``units``, ``value_mg_L``,
    ``value_text``, ``variable_name`` and ``variable_text``.

Sample
    You need to enter the number of records for the user to classify.


The user(s) performing the classification then log into CRATE themselves
and select **User classification**, under **NLP Classification** from the home
page. From here, they can see their assignments in a table. If there are any
records not yet classified, they should be accessible from the link under
**Status**.

Each record is then presented to the user in turn, along with the question and
available answers to the question.

Once classification is complete, the administrator can view and export the
results in a number of formats from the **NLP Classification** home page.
