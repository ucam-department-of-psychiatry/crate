..  crate_anon/docs/source/website_using/database_structure.rst

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
.. _TSV: https://en.wikipedia.org/wiki/Tab-separated_values


.. _database_structure:

Database structure
------------------

You can view the database structure in several ways.

Note that your administrator only has to tell CRATE about the database(s) and
the way they're linked, not about all tables in the database(s) -- CRATE works
out the rest by reading the database(s) directly.


.. _database_structure_online_paginated:

Online in paginated tabular format
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This shows the structure for all databases that CRATE knows about, in a
paginated table. The columns are:

- Schema
- Table
- Column
- Comment
- Data type (e.g. ``VARCHAR(32)``, ``INT(11)``, ``DATETIME``)
- May be NULL?
- Indexed?
- FULLTEXT index?


.. _database_structure_online_singlepage:

Online in single-page tabular format
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is like the :ref:`paginated <database_structure_online_paginated>`
version, but all on one page.

.. warning:: May be slow for large databases.


Online in collapsible tree form
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This shows a list of table names; each one is associated with a table of
details (as above) that can be expanded and collapsed.

.. warning:: May be slow for large databases.


Download in tab-separated values (TSV) format
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The same information as for the :ref:`HTML view
<database_structure_online_singlepage>` described above, but as a TSV_ file.


Download in Excel (.XLSX) format
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The same information as for the :ref:`HTML view
<database_structure_online_singlepage>` described above, but as a single-sheet
`Office Open XML`_ (Excel .XLSX) file.


.. _help_local_database_structure:

Help on local database structure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This simply shows a page defined by your administrator.

(See :ref:`DATABASE_HELP_HTML_FILENAME <DATABASE_HELP_HTML_FILENAME>` in
:ref:`Web config file <web_config_file>`.)
