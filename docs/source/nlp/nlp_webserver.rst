..  crate_anon/docs/source/nlp/nlp_webserver.rst

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

.. _AMQP: http://www.amqp.org
.. _Celery: http://www.celeryproject.org
.. _CherryPy: https://cherrypy.org
.. _Flower: http://flower.readthedocs.io/
.. _Gunicorn: https://gunicorn.org
.. _MySQL: https://www.mysql.com/
.. _Paste: https://pythonpaste.readthedocs.io/
.. _PasteDeploy: https://pastedeploy.readthedocs.io
.. _pserve: https://docs.pylonsproject.org/projects/pyramid/en/latest/pscripts/pserve.html
.. _RabbitMQ: https://www.rabbitmq.com
.. _Redis: https://redis.io
.. _Waitress: https://docs.pylonsproject.org/projects/waitress/
.. _WSGI: https://en.wikipedia.org/wiki/Web_Server_Gateway_Interface


.. _nlp_webserver:

NLPRP web server
----------------

This is CRATE's implementation of a full :ref:`NLPRP <nlprp>` web server. To
use it:

#.  Make sure you have the necessary other software installed and running,
    including Redis_ and (if you wish to use it as your Celery broker)
    RabbitMQ_, plus a database such as MySQL_.

#.  Create a blank database, for storing documents and processing requests
    transiently.

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

#.  Launch the web server, e.g. via crate_nlp_webserver_pserve_ or
    crate_nlp_webserver_launch_gunicorn_.

#.  Launch the Celery workers with crate_nlp_webserver_launch_celery_.


To test it, set up your NLP client for a :ref:`cloud processor
<nlp_config_section_cloud_nlp>`, point it at your server, and try some NLP.
Suppose your :ref:`NLP definition <nlp_config_section_nlpdef>` is called
``cloud_nlp_demo``:

.. code-block:: bash

    # Show what the server's offering:
    crate_nlp --nlpdef cloud_nlp_demo --verbose --print_cloud_processors

    # Run without queuing:
    crate_nlp --nlpdef cloud_nlp_demo --verbose --full --cloud --immediate

    # Run with queuing:
    crate_nlp --nlpdef cloud_nlp_demo --verbose --full --cloud
    crate_nlp --nlpdef cloud_nlp_demo --verbose --full --showqueue
    # crate_nlp --nlpdef cloud_nlp_demo --verbose --full --cancelrequest
    # crate_nlp --nlpdef cloud_nlp_demo --verbose --full --cancelall
    crate_nlp --nlpdef cloud_nlp_demo --verbose --full --retrieve


.. _crate_nlp_webserver_print_demo:

crate_nlp_webserver_print_demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Prints a demo NLP web server config.

.. literalinclude:: _crate_nlp_webserver_print_demo_help.txt
    :language: none


Config file format
~~~~~~~~~~~~~~~~~~

The NLP web server's config file is a PasteDeploy_ file. This system is used to
define WSGI_ applications and servers.

Here's a specimen config file:

.. literalinclude:: _nlp_webserver_demo_config.ini
    :language: ini


Application section
+++++++++++++++++++

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

#.  CRATE NLP web server settings, as follows.


nlp_webserver.secret
####################

*String.*

A secret key for cookies (see `Pyramid AuthTktAuthenticationPolicy
<https://docs.pylonsproject.org/projects/pyramid/en/latest/api/authentication.html>`_;
make one using crate_nlp_webserver_generate_encryption_key_).


sqlalchemy.url
##############

*String.*

The SQLAlchemy URL to your database; see `database URLs
<https://docs.sqlalchemy.org/en/13/core/engines.html>`_.

**Other SQLAlchemy parameters also work;** all begin ``sqlalchemy.` For
example, ``sqlalchemy.echo = True`` enables a debugging feature where all SQL
is echoed.


users_file
##########

*String.*

The path to your user definition file; see crate_nlp_webserver_manage_users_.


processors_path
###############

*String.*

The path to your processor definition file; see :ref:`Processors file format
<nlp_webserver_processors>`.


broker_url
##########

*String.*

The URL to your Celery_ broker server, e.g. via AMQP_, for back-end processing.


backend_url
###########

*String.* Default: None.

The URL to your Celery_ backend database, used to store queuing information.
For the format, see `Celery database URL examples
<https://docs.celeryproject.org/en/latest/userguide/configuration.html#database-url-examples>`_.

- You can ignore this, as it is not necessary to configure a backend for
  Celery, since results are stored elsewhere. See :ref:`Internals
  <nlp_webserver_internals>`.

- If you do want to enable a backend: you can use the same database as above,
  if you wish, or you can create a separate database for Celery.


encryption_key
##############

*String.*

A secret key used for password encryption in the users file. You can make one
with crate_nlp_webserver_generate_encryption_key_.


redis_host
##########

*String.* Default: ``localhost``.

Host for Redis_ database,


redis_port
##########

*Integer.* Default: 6379.

Port for Redis_.


redis_password
##############

*String.* Default: None.

Password for Redis_.


redis_db_number
###############

*Integer.* Default: 0.

Database number for Redis_.


Web server section
++++++++++++++++++

The ``[server:main]`` section defines the web server configuration for the app
named ``main``.

- The ``use`` setting determines which web server should be used.

- Other parameters are passed to the web server in use

Examples include:

- Waitress_:

  .. code-block:: ini

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

.. literalinclude:: _nlp_webserver_demo_processors.py
    :language: python


.. _crate_nlp_webserver_initialize_db:

crate_nlp_webserver_initialize_db
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: _crate_nlp_webserver_initialize_db_help.txt
    :language: none


.. _crate_nlp_webserver_manage_users:

crate_nlp_webserver_manage_users
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: _crate_nlp_webserver_manage_users_help.txt
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

Note that its help (provided by Pyramid's ``pserve`` itself) talks about a file
URI, which might mislead you into thinking you need something like
``file:///home/person/blah.ini``, but actually it wants a filename, like
``/home/person/blah.ini``.

.. literalinclude:: _crate_nlp_webserver_pserve_help.txt
    :language: none


.. _crate_nlp_webserver_launch_gunicorn:

crate_nlp_webserver_launch_gunicorn
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is the preferred alternative to crate_nlp_webserver_pserve_ for launching
the CRATE NLP web server via Gunicorn_ (it stops Gunicorn complaining but
otherwise does the same thing).

.. literalinclude:: _crate_nlp_webserver_launch_gunicorn_help.txt
    :language: none


.. _crate_nlp_webserver_launch_celery:

crate_nlp_webserver_launch_celery
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This launches the Celery_ back-end job controller for the CRATE NLP web server.
It needs to be running for your NLP web server to do any proper work!

.. literalinclude:: _crate_nlp_webserver_launch_celery_help.txt
    :language: none


.. _crate_nlp_webserver_launch_flower:

crate_nlp_webserver_launch_flower
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This command has no options. It launches the Celery Flower_ tool, which is for
monitoring Celery, and associates it with the CRATE NLP web server. It starts a
local web server (by default on port 5555; see :ref:`TCP/IP ports
<tcpip_ports>`); if you browse to http://localhost:5555/ or
http://127.0.0.1:5555/, you can monitor what's happening.


.. _nlp_webserver_internals:

Internal operations: where is your data stored?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- CRATE's NLP web server uses Redis to store web sessions (for user/session
  authentication). No content is stored here.

- It uses Celery for back-end jobs.

  - Celery is configured with a *broker* and a *backend*.
  - The `broker
    <https://docs.celeryproject.org/en/latest/getting-started/first-steps-with-celery.html#choosing-a-broker>`_
    is a messaging system, such as RabbitMQ_ via AMQP_.
  - The `backend
    <https://docs.celeryproject.org/en/latest/getting-started/first-steps-with-celery.html#keeping-results>`_
    is typically a database of jobs. Job results are stored here, but CRATE
    does not use this database for storing job results; it uses a separate
    database (used for storing, transiently, the potentially confidential
    incoming client information and outgoing NLP results).
  - If you want, the Celery backend database can be the same as your main CRATE
    NLP server database (Celery uses tables named ``celery_taskmeta`` and
    ``celery_tasksetmeta``; these do not conflict with CRATE's NLP servertable
    names).

- All client data and all NLP results are stored in a single database.


===============================================================================

.. rubric:: Footnotes

.. [#pastedeployuse]

    CRATE then defines ``paste.app_factory`` in its ``setup.py``, which allows
    PasteDeploy_ to find the actual WSGI app factory.
