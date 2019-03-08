.. crate_anon/docs/source/website_using/sql_helpers.rst

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


.. _sql_helpers:

SQL helpers
-----------

This section helps you generate slightly more laborious queries.


.. _sql_find_text_anywhere:

Find text anywhere
~~~~~~~~~~~~~~~~~~

This looks for text within all text fields. For example, if you elect to search
for "paracetamol", it may generate a query like:

.. code-block:: sql

    SELECT rid
    FROM anonymous_output.table1
    WHERE (
        anonymous_output.table1.textfield1 LIKE '%paracetamol%'
        OR anonymous_output.table1.textfield2 LIKE '%paracetamol%'
        OR anonymous_output.table1.textfield3 LIKE '%paracetamol%'
        OR anonymous_output.table1.textfield4 LIKE '%paracetamol%'
    )
    UNION
    SELECT rid
    FROM anonymous_output.table2
    WHERE (
        anonymous_output.table2.textfield1 LIKE '%paracetamol%'
        OR anonymous_output.table2.textfield2 LIKE '%paracetamol%'
        OR anonymous_output.table2.textfield3 LIKE '%paracetamol%'
        OR anonymous_output.table2.textfield4 LIKE '%paracetamol%'
        OR anonymous_output.table2.textfield5 LIKE '%paracetamol%'
    )
    -- UNION ...

Options include:

- **The field name containing the patient research ID** (:ref:`RID <rid>`),
  which must be consistent across all the tables in the databases that your
  administrator has told.

- **An ID (RID) value;** this is optional but allows you to restrict the query
  to a single patient ("find me all text containing this word for this
  patient").

- **Use full-text indexing where available.** This uses SQL such as ``MATCH``
  (MySQL) or equivalent, rather than ``LIKE``. This restricts you to whole
  words but makes the query much faster for those fields.

- **Minimum "width" of textual fields to include.** You might not want to
  search all 25-character text fields; these are unlikely to be fields designed
  to contain comments by humans. This option allows you to restrict to long
  fields.

- **Include content from fields where found.** This includes the text in the
  output, and makes the query look like:

  .. code-block:: sql

    SELECT
        rid,
        'anonymous_output.table1' AS _table_name,
        'anonymous_output.table1.column1' AS _column_name,
        anonymous_output.table1.column1 AS _content
    FROM anonymous_output.table1
    WHERE anonymous_output.table1.column1 LIKE '%paracetamol%'
    SELECT
        rid,
        'anonymous_output.table2' AS _table_name,
        'anonymous_output.table2.column1' AS _column_name,
        anonymous_output.table2.column1 AS _content
    FROM anonymous_output.table2
    WHERE anonymous_output.table2.column1 LIKE '%paracetamol%'
    -- UNION ...

- **Include date/time where known.** This adds a ``_datetime`` field, which may
  be informative for any tables for which CRATE knows an important date/time
  field.

  (This must be set up by the administrator; see ``default_date_field`` in
  :ref:`Web config file <web_config_file>`.)

- **String fragment to find.** Type in the text to find here.

.. warning::

    These queries may be very slow to run.

    Your administrator may choose to create a view combining the most important
    text fields in your database, or a :ref:`site query <site_queries>`, to
    make this process faster and easier.


.. _sql_find_drug_type:

Find drugs of a given type anywhere
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is an extension of :ref:`Find text anywhere <sql_find_text_anywhere>` and
most of the options are the same. The difference is that instead of looking
for text like "citalopram", you can search for drug classes such as
"antidepressant", and the resulting query will look for anything that matches
its concept of an "antidepressant". That includes matches for generic names and
brand names.

The code used for "drug-finding" is from

- https://cardinalpythonlib.readthedocs.io/

specifically:

- https://cardinalpythonlib.readthedocs.io/en/latest/autodoc/psychiatry/drugs.py.html
- https://cardinalpythonlib.readthedocs.io/en/latest/_modules/cardinal_pythonlib/psychiatry/drugs.html

.. warning::

    This is an experimental feature. Performance is not guaranteed.
