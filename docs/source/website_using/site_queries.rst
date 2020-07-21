..  crate_anon/docs/source/website_using/site_queries.rst

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


.. _site_queries:

Standard site queries
---------------------

The site administrator can create a library of queries that every researcher
can use.

Common "standard" queries might include:

- how many patients are in the de-identified database?
- when was the database last updated?
- when were the associated NLP tables last updated?

These queries can have placeholders, marked out by double square brackets.

For example, the administrator might enter this query:

.. code-block:: sql

    SELECT * FROM anonymous_output.ace WHERE brcid = '[[brcid]]'

and give it a title of "Look up ACE values for a given patient". When the user
runs this query, they are asked to fill in the blank in an HTML form:

.. code-block:: sql

    SELECT * FROM anonymous_output.ace WHERE brcid = '__________'


and after they've entered a ``brcid`` value of ``XYZ``, the query that will be
run is

.. code-block:: sql

    SELECT * FROM anonymous_output.ace WHERE brcid = 'XYZ'

