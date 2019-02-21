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

.. code-block:: none

    usage: crate_launch_cherrypy_server runcpserver [-h] [--version]
                                                    [-v {0,1,2,3}]
                                                    [--settings SETTINGS]
                                                    [--pythonpath PYTHONPATH]
                                                    [--traceback] [--no-color]
                                                    [--host HOST] [--port PORT]
                                                    [--server_name SERVER_NAME]
                                                    [--threads THREADS]
                                                    [--ssl_certificate SSL_CERTIFICATE]
                                                    [--ssl_private_key SSL_PRIVATE_KEY]
                                                    [--log_screen]
                                                    [--no_log_screen]
                                                    [--debug_static]
                                                    [--root_path ROOT_PATH]

    Run this project in a CherryPy webserver. To do this, CherryPy is required
    (pip install cherrypy).

    optional arguments:
      -h, --help            show this help message and exit
      --version             show program's version number and exit
      -v {0,1,2,3}, --verbosity {0,1,2,3}
                            Verbosity level; 0=minimal output, 1=normal output,
                            2=verbose output, 3=very verbose output
      --settings SETTINGS   The Python path to a settings module, e.g.
                            "myproject.settings.main". If this isn't provided, the
                            DJANGO_SETTINGS_MODULE environment variable will be
                            used.
      --pythonpath PYTHONPATH
                            A directory to add to the Python path, e.g.
                            "/home/djangoprojects/myproject".
      --traceback           Raise on CommandError exceptions
      --no-color            Don't colorize the command output.
      --host HOST           hostname to listen on (default: 127.0.0.1)
      --port PORT           port to listen on (default: 8088)
      --server_name SERVER_NAME
                            CherryPy's SERVER_NAME environ entry (default:
                            localhost)
      --threads THREADS     Number of threads for server to use (default: 10)
      --ssl_certificate SSL_CERTIFICATE
                            SSL certificate file (e.g. /etc/ssl/certs/ssl-cert-
                            snakeoil.pem)
      --ssl_private_key SSL_PRIVATE_KEY
                            SSL private key file (e.g. /etc/ssl/private/ssl-cert-
                            snakeoil.key)
      --log_screen          log access requests etc. to terminal (default)
      --no_log_screen       don't log access requests etc. to terminal
      --debug_static        show debug info for static file requests
      --root_path ROOT_PATH
                            Root path to serve CRATE at. Default: /crate

crate_launch_django_server
--------------------------

This is a lightweight test server, using Django_ itself.

Options as of 2016-07-21:

.. code-block:: none

    usage: crate_launch_django_server runserver [-h] [--version] [-v {0,1,2,3}]
                                                [--settings SETTINGS]
                                                [--pythonpath PYTHONPATH]
                                                [--traceback] [--no-color]
                                                [--ipv6] [--nothreading]
                                                [--noreload] [--nostatic]
                                                [--insecure]
                                                [addrport]

    Starts a lightweight Web server for development and also serves static files.

    positional arguments:
      addrport              Optional port number, or ipaddr:port

    optional arguments:
      -h, --help            show this help message and exit
      --version             show program's version number and exit
      -v {0,1,2,3}, --verbosity {0,1,2,3}
                            Verbosity level; 0=minimal output, 1=normal output,
                            2=verbose output, 3=very verbose output
      --settings SETTINGS   The Python path to a settings module, e.g.
                            "myproject.settings.main". If this isn't provided, the
                            DJANGO_SETTINGS_MODULE environment variable will be
                            used.
      --pythonpath PYTHONPATH
                            A directory to add to the Python path, e.g.
                            "/home/djangoprojects/myproject".
      --traceback           Raise on CommandError exceptions
      --no-color            Don't colorize the command output.
      --ipv6, -6            Tells Django to use an IPv6 address.
      --nothreading         Tells Django to NOT use threading.
      --noreload            Tells Django to NOT use the auto-reloader.
      --nostatic            Tells Django to NOT automatically serve static files
                            at STATIC_URL.
      --insecure            Allows serving static files even if DEBUG is False.
