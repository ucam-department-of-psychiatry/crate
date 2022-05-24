..  crate_anon/docs/source/website_config/launch_server.rst

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

.. _CherryPy: https://cherrypy.org/
.. _Django: https://www.djangoproject.com/


Launch the CRATE web server
===========================

.. _crate_launch_cherrypy_server:

crate_launch_cherrypy_server
----------------------------

This is the standard cross-platform production server for CRATE, using
CherryPy_.

The command is a shortcut to :ref:`crate_django_manage runcpserver
<django_manage_runcpserver>`.


.. _crate_launch_django_server:

crate_launch_django_server
--------------------------

This is a lightweight test server, using Django_ itself.

The command is a shortcut to :ref:`crate_django_manage runserver
<django_manage_runserver>`.
