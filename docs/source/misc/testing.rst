..  crate_anon/docs/source/misc/testing.rst

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


.. _pytest: https://docs.pytest.org/en/stable/


Testing
=======

The python code on the server is tested with pytest_

Tests are kept separate to the code they are testing in a ``tests`` sub-folder
with the filename of the module appended with ``_tests.py``. So the module
``crate_anon/anonymise/anonymise.py`` is tested in
``crate_anon/anonymise/tests/anonymise_tests.py``.

Test classes should end in ``Tests`` e.g. ``AnonRegexTests``. Tests that require
an empty database should inherit from ``DatabaseTestCase``.  See
``crate_anon/testing/classes``. Tests that do not require a database can just
inherit from the standard python ``unittest.TestCase``

.. _run_all_tests:

To run all tests whilst in the CRATE virtual environment:

  .. code-block:: bash

      cd crate_anon
      pytest

By default if there is an existing test database, this will be reused.


Custom CRATE pytest options:

--create-test-db      Create a new test database. Necessary when there have been schema changes.
                      Note that the option ``--create-db`` is added by pytest-django and isn't currently used by CRATE.

--database-in-memory  Store the database in memory instead of on disk (SQLite only).
--echo                Log all SQL statements to the default log handler
--db-url              SQLAlchemy test database URL (Not applicable to SQLite).


Some common standard pytest options:

-x           Stop on failure
-k wildcard  Run tests whose classes or files only match the wildcard
-s           Do not capture stdout and stderr. Necessary when debugging with e.g. pdb
--ff         Run previously failed tests first
