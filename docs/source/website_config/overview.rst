.. crate_anon/docs/source/website_config/config.rst

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


Configuring the web front end
=============================

You’ll need to make a new (e.g. MySQL) database for the web front end, and an
admin user with full access rights to it.

Under Windows, run the following in a suitable location.

.. code-block:: bat

    crate_print_demo_crateweb_config > my_crateweb_config.py

Make sure this file is accessible only to you, as it will contain secrets. Edit
it appropriately; see :ref:`Web config file <web_config_file>`. Make the
`CRATE_WEB_LOCAL_SETTINGS` environment variable point to it.

Now, create (or upgrade) the database structure:

.. code-block:: bat

    crate_django_manage migrate

At this point, you should be able to run ``crate_launch_cherrypy_server`` and
browse to http://127.0.0.1:8088/. You’ll also need to run

.. code-block:: bat

    crate_django_manage createsuperuser

You’ll also want to implement SSL (HTTPS) access. In general, a secured
production web site is best implemented via a front-end web server such as
Apache; see :ref:`Configuring for Apache <config_apache>`. You can also use the
CherryPy server, launched with ``crate_launch_cherrypy_server``. For help on
this, run

.. code-block:: bat

    crate_launch_cherrypy_server --help

You can set an environment variable `CRATE_CHERRYPY_ARGS` and the arguments in
this string will be appended to those passed to CherryPy. For example:

.. code-block:: none

    CRATE_CHERRYPY_ARGS=--port 443 --ssl_certificate SSL_CERTIFICATE_FILE --ssl_private_key SSL_PRIVATE_KEY_FILE

If your machine is already using port 443, you may need to use another (e.g.
8443).
