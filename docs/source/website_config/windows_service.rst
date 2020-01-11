.. crate_anon/docs/source/website_config/windows_service.rst

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

.. _Celery: http://www.celeryproject.org/
.. _CherryPy: https://cherrypy.org/


.. _windows_service:

CRATE Windows service
=====================

The most convenient way of running the CRATE web site is via a Windows service.
The service starts both the CRATE internal web server (via CherryPy_) and the
CRATE task queue system (via Celery_). It's the equivalent of running both
:ref:`crate_launch_cherrypy_server <crate_launch_cherrypy_server>` and
:ref:`crate_launch_celery <crate_launch_celery>` together.

To create a Windows service for CRATE, use the ``crate_windows_service``
command. You will need to run it from a command prompt with Administrator
authority.

Logs from the CRATE processes (Celery, CherryPy/Django) go to the normal disk
logs. However, output from the service itself goes to the Windows logs: see
:menuselection:`Event Viewer --> Windows Logs --> Application`.


.. _crate_windows_service:

crate_windows_service
---------------------

Options:

..  literalinclude:: crate_windows_service_help.txt
    :language: none
