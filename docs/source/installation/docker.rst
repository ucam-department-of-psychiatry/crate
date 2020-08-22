..  docs/source/administrator/docker.rst

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

.. _AMQP: https://en.wikipedia.org/wiki/Advanced_Message_Queuing_Protocol
.. _CherryPy: https://cherrypy.org/
.. _Docker: https://www.docker.com/
.. _Docker Compose: https://docs.docker.com/compose/
.. _Flower: https://flower.readthedocs.io/
.. _GATE: https://gate.ac.uk/
.. _Gunicorn: https://gunicorn.org/
.. _MySQL: https://www.mysql.com/
.. _mysqlclient: https://pypi.org/project/mysqlclient/
.. _RabbitMQ: https://www.rabbitmq.com/


.. _crate_docker:

Installing and running CRATE via Docker
=======================================

..  contents::
    :local:
    :depth: 3



Overview
--------

Docker_ is a cross-platform system for running applications in "containers". A
computer (or computing cluster) can run lots of containers. They allow
applications to be set up in standardized and isolated enviroments, which
include their own operating system). The containers then talk to each other,
and to their "host" computer, to do useful things.

The core of Docker is called Docker Engine. The `Docker Compose`_ tool allows
multiple containers to be created, started, and connected together
automatically.

CRATE provides a Docker setup to make installation easy. This uses Docker
Compose to set up several containers, specifically:

- a database system, via MySQL_ on Linux (internal container name ``mysql``);
- a message queue, via RabbitMQ_ on Linux (``rabbitmq``);
- the CRATE web server itself, offering SSL directly via CherryPy_ on Linux
  (``crate_server``);
- the CRATE web site back-end (``crate_workers``);
- a background task monitor, using Flower_ (``crate_monitor``).

Additionally, you can run a number of important one-off command using the
``crate`` Docker image. Apart from CRATE itself, this image also includes:

- Database drivers:

  - MySQL [:ref:`mysqlclient <mysqlclient>`]
  - PostgreSQL [:ref:`psycopg2 <psycopg2>`]
  - SQL Server [:ref:`django-mssql-backend <django_mssql_backend>`,
    :ref:`pyodbc <pyodbc>`, Microsoft ODBC Driver for SQL Server (Linux)]

- External NLP tools:

  - GATE_ (for :ref:`GATE NLP applications <gate_nlp>`)
  - :ref:`KCL BRC Pharmacotherapy <kcl_pharmacotherapy>` tool


Quick start
-----------

#.  Ensure you have Docker and Docker Compose installed (see
    :ref:`prerequisites <docker_prerequisites>`).

#.  Obtain the CRATE source code.

    .. todo::
        Docker/CRATE source: (a) is that the right method? Or should we be
        using ``docker-app``? (Is that experimental?) (b) Document.

#.  Set the :ref:`environment variables <docker_environment_variables>`
    required for Docker operation. (You probably want to automate this with a
    script.)

#.  Change to the ``docker/linux`` directory within the CRATE source tree.

    .. note::
        If you are using a Windows host, change to ``docker/windows``
        instead, and for all the commands below, instead of ``./some_command``,
        run ``some_command.bat``.

#.  Start the containers with:

    .. code-block:: bash

        ./start_crate_docker_interactive

    This gives you an interactive view. As this is the first run, it will also
    create containers, volumes, the database, and so on. It will then encounter
    errors (e.g. config file not specified properly, or the database doesn't
    have the right structure), and will stop.

#.  Run this command to create a demonstration config file with the standard
    name:

    .. todo:: fixme

    .. code-block:: bash

        ./within_docker_venv crate_print_demo_crateweb_config > "${CRATE_DOCKER_CONFIG_HOST_DIR}/crateweb_local_settings.py"

#.  Edit that config file. See :ref:`here <web_config_file>` for a full
    description and :ref:`here <web_config_file_docker>` for special Docker
    requirements.

#.  Create the database structure (tables):

    .. code-block:: bash

        ./within_docker_venv crate_django_manage migrate

#.  Create a superuser:

    .. code-block:: bash

        ./within_docker_venv crate_django_manage createsuperuser

#.  Time to test! Restart with

    .. code-block:: bash

        ./start_crate_docker_interactive

    Everything should now be operational. Using any web browser, you should be
    able to browse to the CRATE site at your chosen host port and protocol,
    and log in using the account you have just created.

#.  When you're satisfied everything is working well, you can stop interactive
    mode (CTRL-C) and instead use

    .. code-block:: bash

        ./start_crate_docker_detached

    which will fire up the containers in the background. To take them down
    again, use

    .. code-block:: bash

        ./stop_crate_docker

You should now be operational! If Docker is running as a service on your
machine, CRATE should also be automatically restarted by Docker on reboot.


.. _docker_prerequisites:

Prerequisites
-------------

You can run Docker on several operating systems. For example, you can run
Docker under Linux (and CRATE will run in Linux-under-Docker-under-Linux).
You can similarly run Docker under Windows (and CRATE will run in
Linux-under-Docker-under-Windows).

- You need Docker Engine installed. See
  https://docs.docker.com/engine/install/.

- You need Docker Compose installed. See
  https://docs.docker.com/compose/install/.


.. _docker_environment_variables:

Environment variables
---------------------

Docker control files are in the ``docker`` directory of the CRATE
source tree. Setup is controlled by the ``docker-compose`` application.

.. note::

    Default values are taken from ``docker/.env``. Unfortunately, this
    name is fixed by Docker Compose, and this file is hidden under Linux (as
    are any files starting with ``.``).


.. _CRATE_DOCKER_CONFIG_HOST_DIR:

CRATE_DOCKER_CONFIG_HOST_DIR
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**No default. Must be set.**

Path to a directory on the host that contains key configuration files. Don't
use a trailing slash.

In this directory, there should be a file called
``crateweb_local_settings.py``, the config file (or, if you have set
CRATE_DOCKER_CRATEWEB_CONFIG_FILENAME_, that filename!).

.. note::
    **Under Windows,** don't use Windows paths like
    ``C:\Users\myuser\my_crate_dir``. Translate this to Docker notation as
    ``/host_mnt/c/Users/myuser/my_crate_dir``. As of 2020-07-21, this doesn't
    seem easy to find in the Docker docs!


.. _CRATE_DOCKER_CRATEWEB_CONFIG_FILENAME:

CRATE_DOCKER_CRATEWEB_CONFIG_FILENAME
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Default: crateweb_local_settings.py*

Base name of the CRATE web server config file (see
CRATE_DOCKER_CONFIG_HOST_DIR_).


CRATE_DOCKER_CRATEWEB_HOST_PORT
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Default: 443*

The TCP/IP port number on the host computer that CRATE should provide an
HTTP or HTTPS (SSL) connection on.

It is strongly recommended that you run CRATE over HTTPS. The two ways of
doing this are:

- Have CRATE run plain HTTP, and connect it to another web server (e.g.
  Apache) that provides the HTTPS component.

  - If you do this, you should **not** expose this port to the "world", since
    it offers insecure HTTP.

  - The motivation for this method is usually that you are running multiple web
    services, of which CRATE is one.

  - We don't provide Apache within Docker, because the Apache-inside-Docker
    would only see CRATE, so there's not much point -- you might as well
    use the next option...

- Have CRATE run HTTPS directly, by specifying the
  :ref:`CRATE_DOCKER_CRATEWEB_SSL_CERTIFICATE
  <CRATE_DOCKER_CRATEWEB_SSL_CERTIFICATE>` and
  :ref:`CRATE_DOCKER_CRATEWEB_SSL_PRIVATE_KEY
  <CRATE_DOCKER_CRATEWEB_SSL_PRIVATE_KEY>` options.

  - This is simpler if CRATE is the only web service you are running on this
    machine. Use the standard HTTPS port, 443, and expose it to the outside
    through your server's firewall. (You are running a firewall, right?)


.. _CRATE_DOCKER_CRATEWEB_SSL_CERTIFICATE:

CRATE_DOCKER_CRATEWEB_SSL_CERTIFICATE
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Default is blank.*


.. _CRATE_DOCKER_CRATEWEB_SSL_PRIVATE_KEY:

CRATE_DOCKER_CRATEWEB_SSL_PRIVATE_KEY
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Default is blank.*


CRATE_DOCKER_FLOWER_HOST_PORT
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Default: 5555*

Host port on which to launch the Flower_ monitor.


.. _CRATE_DOCKER_MYSQL_CRATE_DATABASE_NAME:

CRATE_DOCKER_MYSQL_CRATE_DATABASE_NAME
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Default: crate_web_db*

Name of the MySQL database to be used for CRATE web site data.


.. _CRATE_DOCKER_MYSQL_CRATE_USER_PASSWORD:

CRATE_DOCKER_MYSQL_CRATE_USER_PASSWORD
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**No default. Must be set during MySQL container creation.**

MySQL password for the CRATE database user (whose name is set by
CRATE_DOCKER_MYSQL_CRATE_USER_NAME_).

.. note::
    This only needs to be set when Docker Compose is creating the MySQL
    container for the first time. After that, it doesn't have to be set (and is
    probably best not set for security reasons!).


.. _CRATE_DOCKER_MYSQL_CRATE_USER_NAME:

CRATE_DOCKER_MYSQL_CRATE_USER_NAME
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Default: crate_web_user*

MySQL username for the main CRATE web user. This user is given full control over
the database named in CRATE_DOCKER_MYSQL_CRATE_DATABASE_NAME_. See also
CRATE_DOCKER_MYSQL_CRATE_USER_PASSWORD_.


CRATE_DOCKER_MYSQL_HOST_PORT
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Default: 3306*

Port published to the host, giving access to the CRATE MySQL installation.
You can use this to allow other software to connect to the CRATE database
directly.

This might include using MySQL tools from the host to perform database backups
(though Docker volumes can also be backed up in their own right).

The default MySQL port is 3306. If you run MySQL on your host computer for
other reasons, this port will be taken, and you should change it to something
else.

You should **not** expose this port to the "outside", beyond your host.


.. _CRATE_DOCKER_MYSQL_ROOT_PASSWORD:

CRATE_DOCKER_MYSQL_ROOT_PASSWORD
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**No default. Must be set during MySQL container creation.**

MySQL password for the ``root`` user.

.. note::
    This only needs to be set when Docker Compose is creating the MySQL
    container for the first time. After that, it doesn't have to be set (and is
    probably best not set for security reasons!).


COMPOSE_PROJECT_NAME
~~~~~~~~~~~~~~~~~~~~

*Default: crate*

This is the Docker Compose project name. It's used as a prefix for all the
containers in this project.


.. todo:: fix below here

.. _web_config_file_docker:

The CamCOPS configuration file for Docker
-----------------------------------------

The CamCOPS configuration file is described :ref:`here <server_config_file>`.
There are a few special things to note within the Docker environment.

- **CELERY_BROKER_URL.**
  The RabbitMQ (AMQP_ server) lives in a container named (internally)
  ``rabbitmq`` and uses the default AMQP port of 5672. The
  :ref:`CELERY_BROKER_URL <CELERY_BROKER_URL>` variable should therefore be set
  exactly as follows:

  .. code-block:: none

    CELERY_BROKER_URL = amqp://rabbitmq:5672/
                        ^      ^        ^
                        |      |        |
                        |      |        +- port number
                        |      +- internal name of container running RabbitMQ
                        +- "use AMQP protocol"

- **DB_URL.**
  MySQL runs in a container called (internally) ``mysql`` and the mysqlclient_
  drivers for Python are installed for CamCOPS. (These use C-based MySQL
  drivers for speed). The :ref:`DB_URL <DB_URL>` variable should therefore be
  of the form:

  .. code-block:: none

    DB_URL = mysql+mysqldb://camcops:ZZZ_PASSWORD_REPLACE_ME@mysql:3306/camcops?charset=utf8
             ^     ^         ^       ^                       ^     ^    ^      ^
             |     |         |       |                       |     |    |      |
             |     |         |       |                       |     |    |      +- charset options; don't alter
             |     |         |       |                       |     |    +- database name; should match
             |     |         |       |                       |     |       CAMCOPS_DOCKER_MYSQL_CAMCOPS_DATABASE_NAME
             |     |         |       |                       |     +- port; don't alter
             |     |         |       |                       +- container name; don't alter
             |     |         |       +- MySQL password; should match CAMCOPS_DOCKER_MYSQL_CAMCOPS_USER_PASSWORD
             |     |         +- MySQL username; should match CAMCOPS_DOCKER_MYSQL_CAMCOPS_USER_NAME
             |     +- "use mysqldb [mysqlclient] Python driver"
             +- "use MySQL dialect"

  It remains possible to point "CamCOPS inside Docker" to "MySQL outside
  Docker" (rather than the instance of MySQL supplied with CamCOPS via
  Docker). This would be unusual, but it's up to you.

- **HOST.**
  This should be ``0.0.0.0`` for operation within Docker [#host]_.

- **References to files on disk.**
  CamCOPS mounts a configuration directory from host computer, specified via
  CAMCOPS_DOCKER_CONFIG_HOST_DIR_. From the perspective of the CamCOPS Docker
  containers, this directory is mounted at ``/camcops/cfg``.

  Accordingly, **all user-supplied configuration files should be placed within
  this directory, and referred to via** ``/camcops/cfg``. System-supplied files
  are also permitted within ``/camcops/venv`` (and the demonstration config
  file will set this up for you).

  For example:

  .. code-block:: none

    Host computer:

        /etc
            /camcops
                extra_strings/
                    phq9.xml
                    ...
                camcops.conf
                ssl_camcops.cert
                ssl_camcops.key

    Environment variables for Docker:

        CAMCOPS_DOCKER_CAMCOPS_CONFIG_FILENAME=camcops.conf
        CAMCOPS_DOCKER_CAMCOPS_HOST_PORT=443
        CAMCOPS_DOCKER_CAMCOPS_INTERNAL_PORT=8000
        CAMCOPS_DOCKER_CONFIG_HOST_DIR=/etc/camcops

    CamCOPS config file:

        [site]

        # ...

        EXTRA_STRING_FILES =
            /camcops/venv/lib/python3.6/site-packages/camcops_server/extra_strings/*.xml
            /camcops/cfg/extra_strings/*.xml

        # ...

        [server]

        HOST = 0.0.0.0
        PORT = 8000
        SSL_CERTIFICATE = /camcops/cfg/ssl_camcops.cert
        SSL_PRIVATE_KEY = /camcops/cfg/ssl_camcops.key

        # ...

  CamCOPS will warn you if you are using Docker but your file references are
  not within the ``/camcops/cfg`` mount point.


Using a database outside the Docker environment
-----------------------------------------------

CamCOPS creates a MySQL system and database inside Docker, for convenience.
However, it's completely fine to ignore it and point CamCOPS to a database
elsewhere on your system. Just set the :ref:`DB_URL <DB_URL>` parameter to
point where you want.


Tools
-----

All live in the ``docker`` directory.


bash_within_docker
~~~~~~~~~~~~~~~~~~

Starts a container with the CRATE image and runs a Bash shell within it.

.. warning::

    Running a shell within a container allows you to break things! Be careful.


start_crate_docker_detached
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Shortcut for ``docker-compose up -d``. The ``-d`` switch is short for
``--detach`` (or daemon mode).


start_crate_docker_interactive
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Shortcut for ``docker-compose up --abort-on-container-exit``.

.. note::
    The ``docker-compose`` command looks for a Docker Compose configuration
    file with a default filename; one called ``docker-compose.yaml`` is
    provided.


stop_crate_docker
~~~~~~~~~~~~~~~~~

Shortcut for ``docker-compose down``.


within_docker
~~~~~~~~~~~~~

This script starts a container with the CRATE image, activates the CRATE
virtual environment, and runs a command within it. For example, to explore this
container, you can do

    .. code-block:: bash

        ./within_docker /bin/bash

... which is equivalent to the ``bash_within_docker`` script (see above and
note the warning).


Development notes
-----------------

- See https://camcops.readthedocs.io/en/latest/administrator/docker.html.
