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

.. _LockHunter: https://lockhunter.com/

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
  ``procexp64`` [#procexp64]_.

- Run the Windows Service Manager (if you can’t find it on the menus, run
  ``services.msc`` from the command line). Stop the service named “CRATE web
  service”.

- To see which versions of CRATE are available from PyPI, you can issue an
  “install” command using a nonexistent version number: ``pip install
  crate_anon==999``.

- Install the version you want, e.g.: ``pip install crate_anon==0.18.50``.

  .. warning::

    If you get this error:

    .. code-block:: none

        Could not install packages due to an EnvironmentError: [Errno 13]
        Permission denied: 'c:\\srv\\crate\\crate_virtualenv\\
        Lib\\site-packages\\win32\\servicemanager.pyd' Consider using the
        `--user` option or check the permissions.

    then it means (probably) that you have run the CRATE service via a
    privileged account, which compiled a ``.py`` file to a ``.pyd`` file; the
    ``.pyd`` file is then undeletable by a normal user.

    Delete the offending file and reinstall CRATE. See :ref:`Deleting
    hard-to-delete files <deleting_hard_to_delete_files>` below.

- If there have been database structure changes, or you're not sure, run
  ``crate_django_manage migrate``. See :ref:`crate_django_manage
  <crate_django_manage>`.

- Use Service Manager to restart the CRATE service.

- If it doesn’t start, check the CRATE Django log, fix the problem (maybe your
  configuration file has errors in it), and restart the service.


.. _deleting_hard_to_delete_files:

.. note::

    **Deleting hard-to-delete files under Windows**

    You can try several methods:

    - Try a privileged command prompt. From the Windows Start menu, find
      ``cmd.exe``, right-click it, and choose "Run as administrator". Delete
      the offending file.

    - If that doesn't work, try deleting it via Windows Explorer. You might
      see this:

      .. code-block:: none

        The action can't be completed because the file is open in DHCP Client

        Close the file and try again.

    - Try running ``resmon.exe`` and using :menuselection:`CPU --> Associated
      Handles`, and search for part of the filename [#fileinuse]_.

    - Use ``proxecp64.exe`` and use :menuselection:`Find --> Handle or DLL
      substring` and enter part of a filename, similarly.

    **Best:**

    - Another way is to use LockHunter_. This is pretty helpful! It integrates
      with Windows Explorer, and will offer a reboot-plus-delete if all else
      fails.


.. rubric:: Footnotes

.. [#procexp64]
    Windows Sysinternals Process Explorer:
    https://docs.microsoft.com/en-us/sysinternals/downloads/process-explorer

.. [#fileinuse]
    https://superuser.com/questions/117902/find-out-which-process-is-locking-a-file-or-folder-in-windows
