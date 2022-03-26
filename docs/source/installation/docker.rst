..  docs/source/administrator/docker.rst

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

CRATE provides an installer script to make installation using Docker easy.
The script uses Docker Compose to set up several containers, specifically:

- a database system, via MySQL_ on Linux (internal container name ``mysql``);
- a message queue, via RabbitMQ_ on Linux (``rabbitmq``);
- the CRATE web server itself, offering SSL directly via CherryPy_ on Linux
  (``crate_server``);
- the CRATE web site back-end (``crate_workers``);
- a background task monitor, using Flower_ (``crate_monitor``).
- demonstration source and destination MySQL databases for anonymisation

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

Windows
^^^^^^^

- Install Windows Subsystem for Linux 2 (WSL2):
  https://docs.microsoft.com/en-us/windows/wsl/install. CRATE under WSL2 has
  been tested with Ubuntu 20.04.
- Install Docker Desktop: https://docs.docker.com/desktop/
- Enable WSL2 in Docker Desktop: https://docs.docker.com/desktop/windows/wsl/
- From the Linux terminal install python3-virtualenv:
  Ubuntu: ``sudo apt -y install python3-virtualenv python3-venv``
- See "All platforms" below.


Linux
^^^^^

- Install Docker Engine: https://docs.docker.com/engine/install/
- Install Docker Compose v2 or greater:
  https://docs.docker.com/compose/cli-command/#install-on-linux
- Install python3-virtualenv:

  - Ubuntu: ``sudo apt -y install python3-virtualenv python3-venv``

- See "All platforms" below.


MacOS
^^^^^

- Install Docker Desktop: https://docs.docker.com/desktop/
- Install python3 and python3-virtualenv
- See "All platforms" below.


All platforms
^^^^^^^^^^^^^

The installer can be run interactively, where you will be prompted to enter
settings specific to your CRATE installation. Alternatively you can supply this
information by setting environment variables. This is best done by putting the
settings in a file and executing them before running the installer (e.g.
``source ~/my_crate_settings``).

Here is an example settings file. See :ref:`environment_variables
<docker_environment_variables>` for a description of each setting.

    .. code-block:: bash

        export CRATE_DOCKER_CONFIG_HOST_DIR=${HOME}/crate_config
        export CRATE_DOCKER_GATE_BIOYODIE_RESOURCES_HOST_DIR=${HOME}/bioyodie_resources
        export CRATE_DOCKER_MYSQL_CRATE_USER_PASSWORD=mysqluserpassword
        export CRATE_DOCKER_MYSQL_CRATE_ROOT_PASSWORD=mysqlrootpassword
        export CRATE_DOCKER_MYSQL_CRATE_HOST_PORT=43306
        export CRATE_DOCKER_CRATEWEB_SUPERUSER_USERNAME=admin
        export CRATE_DOCKER_CRATEWEB_SUPERUSER_PASSWORD=adminpassword
        export CRATE_DOCKER_CRATEWEB_SUPERUSER_EMAIL=admin@example.com
        export CRATE_DOCKER_CRATEWEB_USE_HTTPS=1
        export CRATE_DOCKER_CRATEWEB_HOST_PORT=8100
        export CRATE_DOCKER_CRATEWEB_SSL_CERTIFICATE=${HOME}/certs/crate.localhost.crt
        export CRATE_DOCKER_CRATEWEB_SSL_PRIVATE_KEY=${HOME}/certs/crate.localhost.key


To start the installer on all platforms:

    .. code-block:: bash

        curl --location https://github.com/RudolfCardinal/crate/releases/latest/download/installer.sh --fail --output crate_docker_installer.sh && chmod u+x crate_docker_installer.sh && ./crate_docker_installer.sh


.. _docker_environment_variables:

Environment variables
---------------------

.. _CRATE_DOCKER_CONFIG_HOST_DIR:

CRATE_DOCKER_CONFIG_HOST_DIR
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**No default. Must be set.**

Path to a directory on the host that contains key configuration files. Don't
use a trailing slash.

.. note::
    **Under Windows,** don't use Windows paths like
    ``C:\Users\myuser\my_crate_dir``. Translate this to Docker notation as
    ``/host_mnt/c/Users/myuser/my_crate_dir``. As of 2020-07-21, this doesn't
    seem easy to find in the Docker docs! Ensure that this path is within the
    Windows (not WSL2) file system.


.. _CRATE_DOCKER_CRATEWEB_CONFIG_FILENAME:

CRATE_DOCKER_CRATEWEB_CONFIG_FILENAME
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: crateweb_local_settings.py*

Base name of the CRATE web server config file (see
CRATE_DOCKER_CONFIG_HOST_DIR_).


.. _CRATE_DOCKER_CRATEWEB_HOST_PORT:

CRATE_DOCKER_CRATEWEB_HOST_PORT
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**No default: Must be set**

The TCP/IP port number on the host computer that CRATE should provide an
HTTP or HTTPS (SSL) connection on.

It is strongly recommended that you make all connections to CRATE use HTTPS.
The two ways of doing this are:

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


.. _CRATE_DOCKER_CRATEWEB_USE_HTTPS:

CRATE_DOCKER_CRATEWEB_USE_HTTPS
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Access the CRATE web app over HTTPS? (0 = no, 1 = yes)
See CRATE_DOCKER_CRATEWEB_HOST_PORT_ above.


.. _CRATE_DOCKER_CRATEWEB_SSL_CERTIFICATE:

CRATE_DOCKER_CRATEWEB_SSL_CERTIFICATE
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default is blank.*

Filename for an SSL public certificate for HTTPS.
See CRATE_DOCKER_CRATEWEB_HOST_PORT_ above.


.. _CRATE_DOCKER_CRATEWEB_SSL_PRIVATE_KEY:

CRATE_DOCKER_CRATEWEB_SSL_PRIVATE_KEY
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default is blank.*

Filename for an SSL private key file for HTTPS.
See CRATE_DOCKER_CRATEWEB_HOST_PORT_ above.


CRATE_DOCKER_CRATEWEB_SUPERUSER_USERNAME
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

User name for the CRATE administrator, via CRATE's web application.


CRATE_DOCKER_CRATEWEB_SUPERUSER_PASSWORD
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Password for the CRATE administrator, via CRATE's web application.


CRATE_DOCKER_CRATEWEB_SUPERUSER_EMAIL
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Email address for the CRATE administrator.


CRATE_DOCKER_FLOWER_HOST_PORT
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: 5555*

Host port on which to launch the Flower_ monitor.


CRATE_DOCKER_GATE_BIOYODIE_RESOURCES_HOST_DIR
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**No default. Must be set (even if to a dummy directory).**

A directory to be mounted that contains preprocessed UMLS data for the
Bio-YODIE NLP tool (which is part of KConnect/SemEHR, and which runs under
GATE). (You need to download UMLS data and use the
``crate_nlp_prepare_ymls_for_bioyodie`` script to process it. The output
directory used with that command is the directory you should specify here.)
On Windows, ensure this is within the Windows (not WSL2) file system.


.. _CRATE_DOCKER_MYSQL_CRATE_DATABASE_NAME:

CRATE_DOCKER_MYSQL_CRATE_DATABASE_NAME
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: crate_web_db*

Name of the MySQL database to be used for CRATE web site data.


.. _CRATE_DOCKER_MYSQL_CRATE_USER_PASSWORD:

CRATE_DOCKER_MYSQL_CRATE_USER_PASSWORD
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**No default. Must be set during MySQL container creation.**

MySQL password for the CRATE database user (whose name is set by
CRATE_DOCKER_MYSQL_CRATE_USER_NAME_).

.. note::
    This only needs to be set when Docker Compose is creating the MySQL
    container for the first time. After that, it doesn't have to be set (and is
    probably best not set for security reasons!).


.. _CRATE_DOCKER_MYSQL_CRATE_USER_NAME:

CRATE_DOCKER_MYSQL_CRATE_USER_NAME
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: crate_web_user*

MySQL username for the main CRATE web user. This user is given full control over
the database named in CRATE_DOCKER_MYSQL_CRATE_DATABASE_NAME_. See also
CRATE_DOCKER_MYSQL_CRATE_USER_PASSWORD_.


CRATE_DOCKER_MYSQL_CRATE_HOST_PORT
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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


.. _CRATE_DOCKER_MYSQL_CRATE_ROOT_PASSWORD:

CRATE_DOCKER_MYSQL_CRATE_ROOT_PASSWORD
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**No default. Must be set during MySQL container creation.**

MySQL password for the ``root`` user.

.. note::
    This only needs to be set when Docker Compose is creating the MySQL
    container for the first time. After that, it doesn't have to be set (and is
    probably best not set for security reasons!).


COMPOSE_PROJECT_NAME
^^^^^^^^^^^^^^^^^^^^

*Default: crate*

This is the Docker Compose project name. It's used as a prefix for all the
containers in this project.


.. todo:: fix below here; see CamCOPS help

.. _web_config_file_docker:



Tools
-----

All live in the ``installer`` directory.


enter_crate_container.sh
^^^^^^^^^^^^^^^^^^^^^^^^

Starts a container with the CRATE image and runs a Bash shell within it.

.. warning::

    Running a shell within a container allows you to break things! Be careful.


start_crate.sh
^^^^^^^^^^^^^^

Shortcut for ``docker compose up -d``. The ``-d`` switch is short for
``--detach`` (or daemon mode).



stop_crate.sh
^^^^^^^^^^^^^

Shortcut for ``docker compose down``.


run_crate_command
^^^^^^^^^^^^^^^^^

This script starts a container with the CRATE image, activates the CRATE
virtual environment, and runs a command within it. For example, to explore this
container, you can do

    .. code-block:: bash

        ./run_crate_command.sh /bin/bash

... which is equivalent to the ``enter_docker_container`` script (see above and
note the warning).


Development notes
-----------------

- See https://camcops.readthedocs.io/en/latest/administrator/docker.html.
