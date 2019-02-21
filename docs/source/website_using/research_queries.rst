.. crate_anon/docs/source/website_using/research_queries.rst

..  Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).
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

Research queries
----------------

.. warning::

    Research queries use the database connection specified as
    ``DATABASES['research']`` in the Django settings. If users are to see >1
    database, this connection must have appropriate privileges, **and read-only
    access,** or research users might alter or destroy data.

Users can use raw SQL, or some automatic methods of building queries.

Raw SQL mode
~~~~~~~~~~~~

Here, users can edit and save/load SQL queries, run them, and view/save the
tabular output.

They can apply coloured highlighters to specific text occurring anywhere (e.g.
to make it easy to spot the word ‘depression’ in long paragraphs of text).

Query builder
~~~~~~~~~~~~~

The administrator tells the web site about one or several databases that are
accessible via the database connection, including how tables should be linked
on patient (via research IDs), within and across databases. The query builder
assists the user to build simple SELECT / FROM / JOIN / WHERE queries in SQL,
which can be run directly or edited further.

Patient finder
~~~~~~~~~~~~~~

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
