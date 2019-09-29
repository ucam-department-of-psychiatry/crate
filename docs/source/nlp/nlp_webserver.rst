.. crate_anon/docs/source/nlp/nlp_webserver.rst

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

.. _AMQP: http://www.amqp.org
.. _Celery: http://www.celeryproject.org
.. _CherryPy: https://cherrypy.org
.. _Gunicorn: https://gunicorn.org
.. _Paste: https://pythonpaste.readthedocs.io/
.. _PasteDeploy: https://pastedeploy.readthedocs.io
.. _pserve: https://docs.pylonsproject.org/projects/pyramid/en/latest/pscripts/pserve.html
.. _Redis: https://redis.io
.. _Waitress: https://docs.pylonsproject.org/projects/waitress/
.. _WSGI: https://en.wikipedia.org/wiki/Web_Server_Gateway_Interface


.. _nlp_webserver:

NLPRP web server
----------------

This is CRATE's implementation of a full :ref:`NLPRP <nlprp>` web server. To
use it:

#.  Create a blank database, for storing documents and processing requests
    transiently.

#.  Create another blank database, for storing Celery backend information.
    (Optionally, you can skip this step and use your first database for both
    functions.)

#.  Create a blank text file to contain details of your users (with their
    encrypted passwords).

#.  Create a processor definition file with crate_nlp_webserver_print_demo_.
    Edit it.

#.  Create a config file with crate_nlp_webserver_print_demo_. Edit it,
    including pointing it to the database(s), the users file, and the
    processors file, and setting an encryption key (e.g. with
    crate_nlp_webserver_generate_encryption_key_). For more details, see below.

#.  Initialize your empty database with crate_nlp_webserver_initialize_db_,
    pointing it at your config file.

#.  Add a test user with crate_nlp_webserver_manage_users_.

#.  Launch the web server, e.g. via crate_nlp_webserver_pserve_.

    - If you are using Gunicorn_, the preferred syntax is instead
      ``gunicorn --paste <config_file>``.

To test it, set up your NLP client for a :ref:`cloud processor
<nlp_config_section_cloud_nlp>`, point it at your server, and try some NLP.
Suppose your :ref`NLP definition <nlp_config_section_nlpdef>` is called
``cloud_nlp_demo``:

.. code-block:: bash

    # No queuing:
    crate_nlp --nlpdef cloud_nlp_demo --verbose --full --cloud --immediate

    # With queuing:
    crate_nlp --nlpdef cloud_nlp_demo --verbose --full --cloud
    crate_nlp --nlpdef cloud_nlp_demo --verbose --full --showqueue
    crate_nlp --nlpdef cloud_nlp_demo --verbose --full --retrieve


.. _crate_nlp_webserver_print_demo:

crate_nlp_webserver_print_demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Prints a demo NLP web server config.

.. literalinclude:: crate_nlp_webserver_print_demo_help.txt
    :language: none


Config file format
~~~~~~~~~~~~~~~~~~

The NLP web server's config file is a PasteDeploy_ file. This system is used to
define WSGI_ applications and servers.

Here's a specimen config file:

.. literalinclude:: nlp_webserver_demo_config.ini
    :language: ini


Application section
###################

The ``[app:main]`` section defines an *application* named *main*, which is
the default name. Options within this section are provided as keyword arguments
to the WSGI factory; see
:func:`crate_anon.nlp_webserver.wsgi_app.make_wsgi_app` (and its ``settings``
argument) to see how this works.

These options include:

#.  ``use``, which is a PasteDeploy_ setting to say where the code for the
    WSGI application lives. For CRATE's NLP server, this should be
    ``egg:crate_anon`` or ``egg:crate_anon#main`` [#pastedeployuse]_.

#.  Pyramid settings, such as ``pyramid.reload_templates``;

#.  CRATE NLP web server settings:


nlp_webserver.secret
~~~~~~~~~~~~~~~~~~~~

*String.*

A secret key for cookies (see `Pyramid AuthTktAuthenticationPolicy
<https://docs.pylonsproject.org/projects/pyramid/en/latest/api/authentication.html>`_;
make one using crate_nlp_webserver_generate_encryption_key_).


sqlalchemy.url
~~~~~~~~~~~~~~

*String.*

The SQLAlchemy URL to your database; see `database URLs
<https://docs.sqlalchemy.org/en/13/core/engines.html>`_.


users_file
~~~~~~~~~~

*String.*

The path to your user definition file; see crate_nlp_webserver_manage_users_.


processors_path
~~~~~~~~~~~~~~~

*String.*

The path to your processor definition file; see :ref:`Processors file format
<nlp_webserver_processors>`.


broker_url
~~~~~~~~~~

*String.*

The URL to your Celery_ broker server, e.g. via AMQP_, for back-end processing.


backend_url
~~~~~~~~~~~

*String.*

The URL to your Celery_ backend database, used to store queuing information.
For the format, see `Celery database URL examples
<https://docs.celeryproject.org/en/latest/userguide/configuration.html#database-url-examples>`_.


encryption_key
~~~~~~~~~~~~~~

*String.*

A secret key used for password encryption in the users file. You can make one
with crate_nlp_webserver_generate_encryption_key_.


redis_host
~~~~~~~~~~

*String.* Default: ``localhost``.

Host for Redis_ database,


redis_port
~~~~~~~~~~

*Integer.* Default: 6379.

Port for Redis_.


redis_password
~~~~~~~~~~~~~~

*String.* Default: None.

Password for Redis_.


redis_db_number
~~~~~~~~~~~~~~~

*Integer.* Default: 0.

Database number for Redis_.


Web server section
##################

The ``[server:main]`` section defines the web server configuration for the app
named ``main``.

- The ``use`` setting determines which web server should be used.

- Other parameters are passed to the web server in use

Examples include:

- Waitress_:

  .. code-block:: none

    [server:main]
    use = egg:waitress#main
    # ... alternative: use = egg:crate_anon#waitress
    listen = localhost:6543

  For arguments, see `usage
  <https://docs.pylonsproject.org/projects/waitress/en/stable/usage.html>`_
  and `Arguments to waitress.serve
  <https://docs.pylonsproject.org/projects/waitress/en/stable/arguments.html>`_.

- CherryPy_:

  .. code-block:: ini

    [server:main]
    use = egg:crate_anon#cherrypy
    server.socket_host = 127.0.0.1
    server.socket_port = 8080

  For arguments, see `CherryPy: Configure
  <https://docs.cherrypy.org/en/latest/config.html>`_.

- Gunicorn_ (Linux only):

  .. code-block:: ini

    [server:main]
    use = egg:gunicorn#main
    bind = localhost:6543
    workers = 4
    # certfile = /etc/ssl/certs/ca-certificates.crt
    # ssl_version = 5

  For arguments, see `Gunicorn: Settings
  <http://docs.gunicorn.org/en/latest/settings.html#settings>`_.


.. _nlp_webserver_processors:

Processors file format
~~~~~~~~~~~~~~~~~~~~~~

This is a Python file whose job is to define the ``PROCESSORS`` variable.
This is a list of dictionaries in the format shown below. Each dictionary
defines a processor's:

- name;
- descriptive title;
- version string;
- whether this is the default version (used when the client doesn't ask for
  a particular version);
- processor type (e.g. GATE, CRATE);
- schema (database table) information, if known.

As you will see below, CRATE does all this work for you, for its own
processors, via
:func:`crate_anon.nlp_manager.all_processors.all_crate_python_processors_nlprp_processor_info`.

Specimen processors file:

.. literalinclude:: nlp_webserver_demo_processors.py
    :language: python


.. _crate_nlp_webserver_initialize_db:

crate_nlp_webserver_initialize_db
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: crate_nlp_webserver_initialize_db_help.txt
    :language: none


.. _crate_nlp_webserver_manage_users:

crate_nlp_webserver_manage_users
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: crate_nlp_webserver_manage_users_help.txt
    :language: none


.. _crate_nlp_webserver_generate_encryption_key:

crate_nlp_webserver_generate_encryption_key
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Generates a random encryption key and prints it to the screen.


.. _crate_nlp_webserver_pserve:

crate_nlp_webserver_pserve
~~~~~~~~~~~~~~~~~~~~~~~~~~

This is the standard Pyramid pserve_ command. At its most basic, it takes a
single parameter, being the name of your NLP web server config file, and it
starts the web server.


.. literalinclude:: crate_nlp_webserver_pserve_help.txt
    :language: none


===============================================================================

.. rubric:: Footnotes

.. [#pastedeployuse]

    CRATE then defines ``paste.app_factory`` in its ``setup.py``, which allows
    PasteDeploy_ to find the actual WSGI app factory.
