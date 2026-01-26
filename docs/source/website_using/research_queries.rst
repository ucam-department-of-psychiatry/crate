..  crate_anon/docs/source/website_using/research_queries.rst

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

.. _Office Open XML: https://en.wikipedia.org/wiki/Office_Open_XML
.. _SQL: https://en.wikipedia.org/wiki/SQL
.. _TSV: https://en.wikipedia.org/wiki/Tab-separated_values


.. _research_queries:

Research queries
----------------

.. warning::

    Research queries use the database connection specified as
    ``DATABASES['research']`` in the Django settings. If users are to see >1
    database, this connection must have appropriate privileges, **and read-only
    access,** or research users might alter or destroy data.

Users can use raw SQL, or some automatic methods of building queries.

.. _research_query_builder:

Query builder
~~~~~~~~~~~~~

The administrator tells the web site about one or several databases that are
accessible via the database connection, including how tables should be linked
on patient (via research IDs), within and across databases. The query builder
then assists you to build simple SELECT / FROM / JOIN / WHERE queries in SQL,
which can be run directly or edited further.


.. _research_query_sql:

SQL
~~~

SQL_ is the standard language for asking questions of databases. CRATE provides
an interactive way to build SQL queries, but you can also take those queries
and extend them yourself, or just write your own.

Here, you can edit and save/load SQL queries, run them, and view/save the
tabular output.

If you don't know SQL but would like to learn, there are lots of `online SQL
tutorials <https://www.google.com/search?q=sql+tutorial>`_. There are slight
variations in syntax depending on the exact database type you are using, but
the core language is standardized.

.. tip::

    If you enter bad SQL, don't worry. An error message will be generated, but
    you will do no harm (assuming your administrator has configured things
    correctly! See above).


.. _research_query_highlighting:

Highlighting text in results
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here, you can specify text to highlight in different colours in the output.
This makes it easy to spot words in long paragraphs.

For example, you can choose to highlight "insulin" in one colour and "glucose"
in another. The settings you save here affect the display of results for any
research queries that you run.


.. _research_query_results_table:

Results: table view
~~~~~~~~~~~~~~~~~~~

The "standard" way to view the results of a query is as a table in an HTML
page. Each table row is a database row (record). Each table column is a
database column (field). The table is paginated.

:ref:`Highlighting <research_query_highlighting>` will be applied. Long
cells can be collapsed. Cells that are identical to the one above show ditto
marks.

There is a ``Filter`` button through which you can turn the display of
individual columns on or off.


.. _research_query_results_record:

Results: record view
~~~~~~~~~~~~~~~~~~~~

This view may be better than the table view (see above) for detailed inspection
of large records. One page (table) represents a single database record. The
left-hand column contains database column (field) names, and the right-hand
column contains values from the database.


.. _research_query_results_tsv:

Results: tab-separated values (TSV) file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This option offers the results of the currently selected query to download in
tab-separated value (TSV) format.

TSV_ is like comma-separated value (CSV) format, but (as the name suggests)
uses tabs rather than commas to separate columns (which is often helpful
because humans use a lot of commas and not as many tabs when writing text).
Both CSV and TSV files are readily accepted by standard spreadsheet problems
such as LibreOffice Calc and Microsoft Excel.

Only the data is downloaded (compare Excel format, below).


.. _research_query_results_excel:

Results: Excel (.XLSX) file
~~~~~~~~~~~~~~~~~~~~~~~~~~~

This option offers the results of the currently selected query to download in
`Office Open XML`_ format, as used by Microsoft Excel.

The first spreadsheet contains the data; the second contains the SQL and the
time of execution.
