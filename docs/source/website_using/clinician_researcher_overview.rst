..  crate_anon/docs/source/website_using/clinician_researcher_overview.rst

..  Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).
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

.. _crateweb_clinician_researcher_overview:

Overview for clinicians and researchers using the CRATE web interface
---------------------------------------------------------------------

Welcome to CRATE. CRATE creates **de-identified research databases** from
clinical records. Here are some of the things you can do.


For clinicians
~~~~~~~~~~~~~~

There are some special (privileged) functions for clinicians:

- :ref:`Search all text <clinician_privileged_find_text_anywhere>` for an
  identified patient.

- :ref:`Look up research IDs <clinician_privileged_rid_from_pid>` for
  identified patients.

- :ref:`Request that your patient is contacted about a study
  <clinician_privileged_submit_contact_request>`.

Your administrator might also have set up a "standalone" clinician-only
instance of CRATE so that you can use its :ref:`Archive View <archive>` to
browse a read-only copy of a patient's electronic health record (EHR).


For researchers
~~~~~~~~~~~~~~~

**Standard query functions**

- :ref:`Build a database query interactively <research_query_builder>`

- :ref:`Write your own SQL queries <research_query_sql>`

- :ref:`Highlight text in results <research_query_highlighting>`

- :ref:`View query results in a standard table <research_query_results_table>`

- :ref:`View query results in a "record-wise" table
  <research_query_results_record>`

- Download query results in :ref:`TSV <research_query_results_tsv>` or
  :ref:`Excel <research_query_results_excel>` format

**Patient Explorer**

- Use a :ref:`Patient Explorer <patient_explorer>` query to find patients in
  the de-identified database.

**More query functions**

- Use :ref:`SQL helpers <sql_helpers>` to aid you in constructing lengthy
  queries.

- Use standard :ref:`site queries <site_queries>`, defined by your local
  database administrator, to answer commonly asked questions about your
  local data.

**Database structure**

- Ask CRATE to show you the :ref:`structure of your database
  <database_structure>` in different ways.

**Archive view**

- Use the :ref:`Archive View <archive>` to browse a de-identified record like
  a front-end electronic health record (EHR).


For researchers wishing to re-identify and contact patients
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- :ref:`View and manage studies <c4c_view_manage_studies>` that you are part
  of.

- :ref:`Submit contact requests <c4c_submit_contact_request>`, seeking to
  re-identify and communicate with patients subject to their explicit consent.


Your settings
~~~~~~~~~~~~~

Change your settings
####################

You can change your display formatting settings here (such as the default
number of items to show per page, and how long textual result fields need to be
before the site "collapses" the result so you have to click to see everything).


Change your password
####################

You can change your CRATE password here.


About CRATE
~~~~~~~~~~~

Show information about your CRATE server, including:

- a link to this documentation at https://crateanon.readthedocs.io/;
- the CRATE version your server is running;
- how to cite CRATE in publications;
- links to the CRATE source code and Python package;
- third-party licence details.
