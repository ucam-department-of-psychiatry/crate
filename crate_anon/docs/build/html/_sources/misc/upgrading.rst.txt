.. crate_anon/docs/source/misc/upgrading.rst

..  Copyright (C) 2015-2018 Rudolf Cardinal (rudolf@pobox.com).
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

Upgrading CRATE
===============

Under Windows:

- Activate your CRATE virtual environment. We use a batch file to do this, but
  from the command prompt, the command will be something like
  ``C:\srv\crate\crate_virtualenv\Scripts\activate``. (If you use a batch file,
  you must ``CALL`` this activation script.) If you want to check which Python
  virtual environment is activated, you can do this:

  .. code-block:: bat

    python

  .. code-block:: python

    import sys
    print(sys.executable)

- You can show current version numbers with ``pip freeze``.

- Make sure that nobody’s doing anything important! You could use tools like
  `procexp64` [#procexp64]_.

- Run the Windows Service Manager (if you can’t find it on the menus, run
  ``services.msc`` from the command line). Stop the service named “CRATE web
  service”.

- To see which versions of CRATE are available from PyPI, you can issue an
  “install” command using a nonexistent version number: ``pip install
  crate_anon==999``.

- Install the version you want, e.g.: ``pip install crate_anon==0.18.50``.

- Use Service Manager to restart the CRATE service.

- If it doesn’t start, check the CRATE Django log, fix the problem (maybe your
  configuration file has errors in it), and restart the service.


.. rubric:: Footnotes

.. [#procexp64]
    Windows Sysinternals Process Explorer:
    https://docs.microsoft.com/en-us/sysinternals/downloads/process-explorer
