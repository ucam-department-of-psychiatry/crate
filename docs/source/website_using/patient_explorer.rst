..  crate_anon/docs/source/website_using/patient_explorer.rst

..  Copyright (C) 2015-2020 Rudolf Cardinal (rudolf@pobox.com).
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
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.


.. _patient_explorer:

Patient Explorer queries
------------------------

A Patient Explorer is a specialized :ref:`research query <research_queries>`
to assist you in finding *patients* in the de-identified research database.

An example might be:

- "Find me all patients whose free text contains the word 'mirtazapine'."

*Note -- not "all mentions of the word 'mirtazapine'".*

You can do more:

- "Find me all patients whose free text contains the word 'mirtazapine',
  and show me their age."

The Patient Explorer is a **two-stage query.**

#. The first query finds patients meeting a certain criterion.

#. The second query (or queries) finds information the user wants about the
   patients from the first stage.


.. note::

    Internally, the
    :class:`crate_anon.crateweb.research.models.PatientExplorer` class contains
    a :class:`crate_anon.crateweb.research.models.PatientMultiQuery`, which
    does the interesting work.


.. _patient_explorer_build:

Build a Patient Explorer
~~~~~~~~~~~~~~~~~~~~~~~~

There is a page to help you build a Patient Explorer.

In ``A. Output columns``, choose what you'd like to see about the patients.
(This corresponds to the *second*-stage query.)

In ``B. Patient selection criteria``, choose what needs to be true about these
patients to let them "through" the filter. (This corresponds to the
*first*-stage query.)

Alternatively, instead of ``B``, specify ``C. Manual patient selection query``
by typing an SQL query in. The objective is for this query to return a unique
list of master research IDs (MRIDs) for relevant patients.


.. _patient_explorer_choose:

Choose Patient Explorer
~~~~~~~~~~~~~~~~~~~~~~~

This page lets you choose and re-run Patient Explorers that you built earlier
(see above).


.. _patient_explorer_data_finder_results:

Data Finder: results
~~~~~~~~~~~~~~~~~~~~

This view summarizes where relevant data was found.

It shows a short table with the following columns:

- row number
- ``master_research_id``
- ``table_name``
- ``n_records``
- ``min_date``
- ``max_date``

The ``table_name`` column can be any table for which output was requested (see
:ref:`Build a Patient Explorer <patient_explorer_build>`).

.. note::

    See
    :meth:`crate_anon.crateweb.research.models.PatientMultiQuery.gen_data_finder_queries`.


.. _patient_explorer_data_finder_excel:

Data Finder: Excel
~~~~~~~~~~~~~~~~~~

This option allows you to download the :ref:`Data Finder results
<patient_explorer_data_finder_results>` in Excel XLSX format.

- The first spreadsheet contains data for all patients.
- The second spreadsheet shows the SQL used and its execution time.
- The third and subsequent sheet(s) show data for individual patients, one
  per sheet.

.. note::

    See
    :func:`crate_anon.crateweb.research.models.PatientMultiQuery.data_finder_excel`.


Table Browser
~~~~~~~~~~~~~

This view shows a list of all tables from the output, with hyperlinks. When
you click on a table, it launches a view to show the Patient Explorer data from
just that table.


Monster Data
~~~~~~~~~~~~

This view shows data from **all** output tables of the Patient Explorer,
consecutively, for **one patient per page.**


More detail on the Patient Explorer concept
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Following the CRIS web front end, it can sometimes be helpful to view specific
records *for patients* meeting specific criteria. The CRIS system uses XML data
for its web front end, and that XML is organized on a per-patient basis, so its
logical organization is: (a) specify criteria that each *patient* must meet;
(b) specify fields shown for *those patients*; and (c) present them in a
non-standard tabular form, essentially laying out multiple tables side by side
[#crisquerylayout]_.

From CRATE’s perspective, operating with relational databases directly, there
are two ways of approaching  this problem – particularly part (c). The first is
a UNION query [#unionexample]_; this allows plain SQL, but doesn’t sit well
with attempts to preserve multi-column table information (because all SELECT
statements contributing to a UNION must have the same number of columns). The
second is to fetch results from multiple tables separately and combine/present
them in Python, using ‘patient’ as the explicit basis.

The first option is always available for manual use, because CRATE supports
arbitrary SQL queries.

The second option is supported in a more friendly fashion. The logical steps
are:

- A *patient ID query* is built. Patient IDs are found, using the RID/TRID,
  according to selection criteria specified by the user. For example, one can
  specify ``diagnosis LIKE 'F20%'`` to find records of patients with an ICD-10
  code starting with F20 (schizophrenia). The patient-finding is done by
  checking for at least one such record. If multiple criteria are specified,
  they are joined as desired (e.g. with AND or OR) [#patientidquery]_.

- Output fields are specified (e.g. diagnosis from the diagnosis table;
  progress notes from the progress notes table).

- CRATE runs one query *per table*; essentially, ``SELECT specified_fields FROM
  one_of_the_tables WHERE rid IN (patient_id_query)``.

- CRATE displays several tables jointly: from left to right, `patient_id |
  table1 | table2`, split into meta-rows by patient ID. For saving, it creates
  a XLSX spreadsheet.


===============================================================================

.. rubric:: Footnotes

.. [#crisquerylayout]
    For example, if you ask it to present patient research IDs, diagnoses, and
    notes, then if patient 1 has three diagnoses and 10 notes, you might get
    the patient number in column 1; the first 10 rows are for that patient; the
    ‘diagnosis’ column has three entries; the ‘notes’ column has 10 entries.
    This is quite different from a simple SQL JOIN, which would attempt to
    create rows for every combination (here, 3 diagnoses × 10 notes = 30 rows
    for that patient).

.. [#unionexample]
    For example:

    .. code-block:: sql

        SELECT
            rid,
            'diagnosis' AS column_name,
            diagnosis AS value
        FROM diagnosis_table
        WHERE rid IN (SELECT rid FROM some_table WHERE some_criterion)
        UNION
        SELECT
            rid,
            'note' AS column_name,
            note AS value
        FROM progress_note_table
        WHERE rid IN (SELECT rid FROM some_table WHERE some_criterion)
        ;

.. [#patientidquery]
    For example:

    .. code-block:: sql

        SELECT DISTINCT mrid
        FROM master_id_table
        INNER JOIN diagnosis_table
            ON diagnosis_table.trid  = master_id_table.trid
        INNER JOIN progress_note_table
            ON progress_note_table.trid = master_id_table.trid
        WHERE
            diagnosis_table.diagnosis LIKE 'F20%'
            AND progress_note_table.note LIKE '%depression%'
        ;
