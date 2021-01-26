..  crate_anon/docs/source/website_config/apache.rst

..  Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).
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


.. _config_apache:

Configuring for Apache
======================

Apache is a powerful but fairly complex web server. A suggested method of using
it with CRATE under Windows is as follows:

- Note that Windows configuration files for Apache are typically
  ``C:\Apache24\conf\httpd.conf`` (the master configuration file) and
  ``C:\Apache24\conf\extra\httpd-ssl.conf`` (included by the master file).

- Ensure you set up HTTPS correctly.

- Disable anything relating to CRATE on plain HTTP.

- Pick a URL stem such as `/crate` at which to serve CRATE.

- Route CRATE through an internal TCP port – let’s say 8999 – such that CRATE’s
  CherryPy server talks to port 8999 (via plain HTTP), the main Apache server
  talks to the world on the normal HTTPS port 443, and Apache talks to port
  8999 behind the scenes and encrypts the external traffic.

- This is slightly tricky. CherryPy needs to think it’s mounted at /, because
  Apache is going to strip off the prefix. It also needs to talk on the correct
  path. To get CherryPy to do this for CRATE, set the environment variable
  ``CRATE_CHERRYPY_ARGS=--port 8999 --root_path /`` before you launch the CRATE
  Windows service. The overview is like this:

.. code-block:: none

    User visits       https://mysite.mydomain/crate/XYZ

    Apache: public    (1) Receive request for https://mysite.mydomain/crate/XYZ
    Apache: internal  - decrypt from HTTPS (SSL)
                      - take path as ‘/crate/XYZ’
                      - notice that ‘/crate’ is being proxied
                      - ProxyPass: send path ‘/XYZ’ to internal address of http://127.0.0.1:8999
                      ... request goes to internal (e.g. CherryPy) web server and results come back...
                      - ProxyPassReverse: rewrite URLs in headers going back to the user,
                            e.g. ‘/login’ -> ‘/crate/login’
                      - encrypt to HTTPS (SSL) when returning to user

    CherryPy          “I am based at /, so interpret path /XYZ as being one of mine.”
                      - The ‘/’ comes from the --root_path option to CherryPy.

    Django            “Do something with path /XYZ.”
                      “If I need to send an absolute URL to the user, I need to prepend
                          ‘https://mysite.mydomain/crate’ to it.”
                      - This information comes from the DJANGO_SITE_ROOT_ABSOLUTE_URL
                        and FORCE_SCRIPT_NAME settings for CRATE.

    And also, for static serving:

    Apache: public    (2) Receive request for https://mysite.mydomain/crate_static/PQR
    Apache: internal  - decrypt from HTTPS (SSL)
                      - take path as ‘/crate_static/PQR’
                      - notice that ‘/crate_static’ is being aliased to a directory full of static files
                      - serve ‘PQR’ from the configured static directory
                      - encrypt to HTTPS (SSL)

So...

- Ensure Apache has `mod_proxy` loaded. Under Windows, achieve this by
  uncommenting these lines from `httpd.conf`:

    .. code-block:: apacheconf

        LoadModule proxy_module modules/mod_proxy.so
        LoadModule proxy_http_module modules/mod_proxy_http.so

- Add to your Apache SSL config section (NB: ONLY in the SSL/HTTPS section!)
  like this:

    .. code-block:: apacheconf

            # Definitions to make things clearer
        Define CRATE_VISIBLE_PATH /crate
        Define CRATE_INTERNAL_URL http://127.0.0.1:8999
        Define CRATE_STATIC_PATH /crate_static
        Define CRATE_STATIC_ROOT “C:/srv/src/crate/crate_anon/crateweb/static_collected”
            # ... for UNIX sockets, you might use this instead of CRATE_INTERNAL_URL:
        Define CRATE_UNIX_SOCKET unix:/tmp/.crate_gunicorn.sock
        Define CRATE_DUMMY_HOST_URL http://cratedummy/

            # Don’t ProxyPass the static files; serve them directly via Apache
        ProxyPassMatch ^${CRATE_STATIC_PATH} !

            # Set a timeout in seconds (default is the value of Timeout, whose default is 60)
            # If your users can run slow queries, increase this:
        ProxyTimeout 600

            # Proxy through to CRATE
            # (a) route the URLs
            #     ... “retry=0” prevents Apache disabling the connection for a while on failure
        ProxyPass ${CRATE_VISIBLE_PATH} ${CRATE_INTERNAL_URL} retry=0
        ProxyPassReverse ${CRATE_VISIBLE_PATH} ${CRATE_INTERNAL_URL}
            #     ... or to use UNIX sockets:
        # ProxyPass ${CRATE_VISIBLE_PATH} ${CRATE_UNIX_SOCKET}|${CRATE_DUMMY_HOST_URL} retry=0
        # ProxyPassReverse ${CRATE_VISIBLE_PATH} ${CRATE_UNIX_SOCKET}|${CRATE_DUMMY_HOST_URL}
            #     ... see the special methods for Unix Domain Sockets at
            #         https://httpd.apache.org/docs/trunk/mod/mod_proxy.html#proxypass

            # (b) provide permission
        <Location ${CRATE_VISIBLE_PATH}>
            Require all granted
        </Location>

            # Serve static files directly from Apache
            # (a) route the URL
        Alias ${CRATE_STATIC_PATH} “${CRATE_STATIC_ROOT}”
            # (b) provide permission
        <Location ${CRATE_STATIC_PATH}>
            Require all granted
        </Location>
        <Directory “${CRATE_STATIC_ROOT}”>
            Require all granted
        </Directory>

- Tell CRATE where it’s been mounted (so it can offer URLs to itself
  correctly). In the Django :ref:`local settings <web_config_file>` (q.v.):

    .. code-block:: python

        DJANGO_SITE_ROOT_ABSOLUTE_URL = "https://myresearchdb.mysite.mydomain"  # no “/crate” suffix here
        FORCE_SCRIPT_NAME = "/crate"

- Restart Apache.

- For testing, run :ref:`crate_launch_cherrypy_server
  <crate_launch_cherrypy_server>` from the command line. You should see your
  access requests here.

- Test static serving with e.g.
  https://myresearchdb.mysite.mydomain/crate_static/yellow.png.
