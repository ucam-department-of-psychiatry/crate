.. crate_anon/docs/source/website_config/launch_server.rst

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

.. _CherryPy: https://cherrypy.org/
.. _Django: https://www.djangoproject.com/


Launch the CRATE web server
===========================

.. _crate_launch_cherrypy_server:

crate_launch_cherrypy_server
----------------------------

This is the standard cross-platform production server for CRATE, using
CherryPy_.

Options as of 2016-07-21:

..  literalinclude:: crate_launch_cherrypy_server_help.txt
    :language: none


crate_launch_django_server
--------------------------

This is a lightweight test server, using Django_ itself.

Options as of 2016-07-21:

..  literalinclude:: crate_launch_django_server_help.txt
    :language: none
