..  docs/source/administrator/docker.rst

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

.. _AMQP: https://en.wikipedia.org/wiki/Advanced_Message_Queuing_Protocol
.. _Celery: https://docs.celeryq.dev/en/stable/
.. _CherryPy: https://cherrypy.org/
.. _Docker: https://www.docker.com/
.. _Docker Compose: https://docs.docker.com/compose/
.. _Flower: https://flower.readthedocs.io/
.. _GATE: https://gate.ac.uk/
.. _Gunicorn: https://gunicorn.org/
.. _MySQL: https://www.mysql.com/
.. _mysqlclient: https://pypi.org/project/mysqlclient/
.. _RabbitMQ: https://www.rabbitmq.com/
.. _Start containers automatically: https://docs.docker.com/engine/containers/start-containers-automatically/


.. _crate_docker:

Installing and running CRATE via Docker (recommended)
=====================================================

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

CRATE provides an installer script to make installation using Docker simpler.
The installer uses Docker Compose to set up several containers, specifically:

+-------------------------+--------------------------------------------------------------------------+
| Name                    | Description                                                              |
+=========================+==========================================================================+
| ``crate_crate_server``  | Runs the various CRATE commands for anonymisation etc and                |
|                         | provides the web server for the CRATE web application,                   |
|                         | offering SSL directly via CherryPy_.                                     |
+-------------------------+--------------------------------------------------------------------------+
| ``crate_crate_workers`` | Processes background tasks for the CRATE web application via Celery_     |
+-------------------------+--------------------------------------------------------------------------+
| ``crate_rabbit_mq``     | Message queue, via RabbitMQ_.                                            |
+-------------------------+--------------------------------------------------------------------------+
| ``crate_flower``        | Background task monitor, using Flower_.                                  |
+-------------------------+--------------------------------------------------------------------------+
| ``crate_crate_db``      | An optional database container for the CRATE web                         |
|                         | application via MySQL_ if you have not provided your own.                |
+-------------------------+--------------------------------------------------------------------------+
| ``crate_source_db``     | Optional MySQL databases used to demonstrate anonymisation with          |
| ``crate_research_db``   | CRATE. See                                                               |
| ``crate_secret_db``     | :ref:`Data and database prerequisites <data_and_database_prerequisites>` |
+-------------------------+--------------------------------------------------------------------------+

The installer will generate the configuration files for anonymisation and the
CRATE web application, build and start the Docker containers. If you have opted
for the installer to create the demonstration databases it will also create some
fictitious patient records and anonymise them.

The installer also copies example Bash scripts for anonymisation etc to the
``scripts`` directory of the CRATE file system. These can be modified as
required.


.. _quick_start:

Quick start
-----------

Linux
^^^^^

- Install Docker Engine: https://docs.docker.com/engine/install/
- Install Docker Compose v2 or greater:
  https://docs.docker.com/compose/cli-command/#install-on-linux
- Install python3-virtualenv:

  - Ubuntu: ``sudo apt -y install python3-virtualenv python3-venv``

- See :ref:`All platforms <all_platforms>`.


Windows
^^^^^^^

Note that whilst CRATE will run under Docker Desktop and Windows Subsystem for
Linux 2 (WSL2) on Windows, this is not well-suited to an environment where
several Windows users can access the same instance of CRATE. To work around this
you could designate a single Windows account to be shared by multiple users.

- Install Windows Subsystem for Linux 2 (WSL2):
  https://docs.microsoft.com/en-us/windows/wsl/install.
- Install Docker Desktop: https://docs.docker.com/desktop/
- Enable WSL2 in Docker Desktop: https://docs.docker.com/desktop/windows/wsl/
- From the Linux terminal install python3-virtualenv:
  Ubuntu: ``sudo apt -y install python3-virtualenv python3-venv``
- See :ref:`All platforms <all_platforms>`


MacOS
^^^^^

- Install Docker Desktop: https://docs.docker.com/desktop/
- Install python3 and python3-virtualenv
- See :ref:`All platforms <all_platforms>`.


.. _all_platforms:

All platforms
^^^^^^^^^^^^^

The installer can be run interactively, where you will be prompted to enter
settings specific to your CRATE installation. The installer will save these
settings as environment variables and will also write these to a file, which you
can execute before the next time you run the installer (e.g. ``source
/crate/config/set_crate_docker_host_envvars``). If you prefer, you can create
this file yourself and ``source`` it before running the installer. See
:ref:`Example settings file <example_settings_file>`

To start the installer on all platforms, run the below command, replacing
``/path/to/top/level/crate/dir`` with the top-level directory where CRATE
should be installed. The installer will create this if it doesn't exist but it
will need to be writeable by the user running the installer.

    .. code-block:: bash

        curl --location https://github.com/ucam-department-of-psychiatry/crate/releases/download/latest/installer_boot.py --fail --output installer_boot.py && chmod u+x installer_boot.py && python3 installer_boot.py --crate_root_dir /path/to/top/level/crate/dir


.. _example_settings_file:

Example settings file
^^^^^^^^^^^^^^^^^^^^^

Here is an example settings file. See :ref:`environment_variables
<docker_environment_variables>` and :ref:`environment_variables
<installer_environment_variables>` for a description of each setting.

    .. code-block:: bash

        export CRATE_DOCKER_CONFIG_HOST_DIR=/crate/config
        export CRATE_DOCKER_CRATEWEB_HOST_PORT=8100
        export CRATE_DOCKER_CRATEWEB_SUPERUSER_EMAIL=admin@example.com
        export CRATE_DOCKER_CRATEWEB_SUPERUSER_PASSWORD=adminpassword
        export CRATE_DOCKER_CRATEWEB_SUPERUSER_USERNAME=admin
        export CRATE_DOCKER_CRATE_DB_DATABASE_NAME="crate_web_db"
        export CRATE_DOCKER_FILES_HOST_DIR=/crate/files
        export CRATE_DOCKER_GATE_BIOYODIE_RESOURCES_HOST_DIR=/crate/bioyodie_resource
        export CRATE_DOCKER_RESEARCH_DATABASE_NAME="research"
        export CRATE_DOCKER_SECRET_DATABASE_NAME="secret"
        export CRATE_DOCKER_SOURCE_DATABASE_NAME="source"
        export CRATE_DOCKER_STATIC_HOST_DIR="/crate/static"

        export CRATE_INSTALLER_CRATEWEB_USE_HTTPS="0"
        export CRATE_INSTALLER_CRATE_DB_ENGINE="mysql"
        export CRATE_INSTALLER_CRATE_DB_PORT="3306"
        export CRATE_INSTALLER_CRATE_DB_SERVER="crate_db"
        export CRATE_INSTALLER_CRATE_ROOT_HOST_DIR="/crate"
        export CRATE_INSTALLER_CREATE_CRATE_DB_CONTAINER="0"
        export CRATE_INSTALLER_CREATE_DEMO_DB_CONTAINERS="0"
        export CRATE_INSTALLER_RESEARCH_DATABASE_ENGINE="mysql"
        export CRATE_INSTALLER_RESEARCH_DATABASE_HOST="research_db_host"
        export CRATE_INSTALLER_RESEARCH_DATABASE_PORT="3306"
        export CRATE_INSTALLER_SECRET_DATABASE_ENGINE="mysql"
        export CRATE_INSTALLER_SECRET_DATABASE_HOST="secret_db_host"
        export CRATE_INSTALLER_SECRET_DATABASE_PORT="3306"
        export CRATE_INSTALLER_SOURCE_DATABASE_ENGINE="mysql"
        export CRATE_INSTALLER_SOURCE_DATABASE_HOST="source_db_host"
        export CRATE_INSTALLER_SOURCE_DATABASE_PORT="3306"


.. _docker_environment_variables:

Docker Environment variables
----------------------------

The Docker environment variables with prefix ``CRATE_DOCKER`` are used by both
the CRATE installer and the running Docker instance. For some of these settings,
where it would be unusual to change them from their defaults, they can only be
overridden if set explicitly before running the installer. For other settings,
the installer will prompt you to enter them if not already set.


.. _CRATE_DOCKER_CONFIG_HOST_DIR:

CRATE_DOCKER_CONFIG_HOST_DIR
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Required by Docker. The installer will set this to* ``${CRATE_INSTALLER_CRATE_ROOT_HOST_DIR}/config``.

Path to a directory on the host that contains key configuration files. Don't
use a trailing slash.

.. note::
    **Under Windows,** don't use Windows paths like
    ``C:\Users\myuser\my_crate_dir``. Translate this to Docker notation as
    ``/host_mnt/c/Users/myuser/my_crate_dir``. As of 2020-07-21, this doesn't
    seem easy to find in the Docker docs! Ensure that this path is within the
    Windows (not WSL2) file system.


CRATE_DOCKER_CRATE_ANON_CONFIG
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: crate_anon_config.ini*

Base name of the CRATE anonymisation config file (see CRATE_DOCKER_CONFIG_HOST_DIR_).


CRATE_DOCKER_CRATE_CHERRYPY_ARGS
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: --host 0.0.0.0 --port 8000*

Arguments to pass to the CherryPy web server, which hosts the CRATE Django web
application.


CRATE_DOCKER_CRATE_DB_DATABASE_NAME
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: crate_web_db*

Name of the database used by the CRATE web application, either the one provided
running in a MySQL Docker container or your own.


.. _CRATE_DOCKER_CRATE_DB_USER_NAME:

CRATE_DOCKER_CRATE_DB_USER_NAME
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: crate_web_user*

The name of the database user used to access the CRATE web application database.


.. _CRATE_DOCKER_CRATE_DB_USER_PASSWORD:

CRATE_DOCKER_CRATE_DB_USER_PASSWORD
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**No default. Must be set during MySQL container creation.**

Password for the CRATE database user (whose name is set by
CRATE_DOCKER_CRATE_DB_USER_NAME_).

.. note::
    This only needs to be set when Docker Compose is creating the MySQL
    container for the first time. After that, it doesn't have to be set (and is
    probably best not set for security reasons!).


CRATE_DOCKER_CRATE_DB_HOST_PORT
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: 3306*

When using the provided MySQL CRATE web application database running under
Docker, this is the port on the host where this database can be accessed.

The default MySQL port is 3306. If you run MySQL on your host computer for
other reasons, this port will be taken, and you should change it to something
else.

You should **not** expose this port to the "outside", beyond your host.


CRATE_DOCKER_CRATE_WAIT_FOR
^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: rabbitmq:5672*

A space separated list of host:port entries of Docker containers that the CRATE
server should wait for before starting up. If needed, the installer will append
to this the provided MySQL CRATE web application database
and any demonstration databases running under Docker.


.. _CRATE_DOCKER_CRATEWEB_CONFIG_FILENAME:

CRATE_DOCKER_CRATEWEB_CONFIG_FILENAME
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: crateweb_local_settings.py*

Base name of the CRATE web server config file (see CRATE_DOCKER_CONFIG_HOST_DIR_).


.. _CRATE_DOCKER_CRATEWEB_HOST_PORT:

CRATE_DOCKER_CRATEWEB_HOST_PORT
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: 8000*

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
  CRATE_INSTALLER_CRATEWEB_SSL_CERTIFICATE_ and
  CRATE_INSTALLER_CRATEWEB_SSL_PRIVATE_KEY_ options.

  - This is simpler if CRATE is the only web service you are running on this
    machine. Use the standard HTTPS port, 443, and expose it to the outside
    through your server's firewall. (You are running a firewall, right?)


CRATE_DOCKER_CRATEWEB_SUPERUSER_EMAIL
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Email address for the CRATE administrator.


CRATE_DOCKER_CRATEWEB_SUPERUSER_PASSWORD
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Password for the CRATE administrator, via CRATE's web application.


CRATE_DOCKER_CRATEWEB_SUPERUSER_USERNAME
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

User name for the CRATE administrator, via CRATE's web application.


.. _CRATE_DOCKER_FILES_HOST_DIR:

CRATE_DOCKER_FILES_HOST_DIR
^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Required by Docker. The installer will set this to* ``${CRATE_INSTALLER_CRATE_ROOT_HOST_DIR}/files``.

Path to a directory on the host for general file storage e.g. binary files
uploaded to CRATE, such as PDFs.


CRATE_DOCKER_FLOWER_HOST_PORT
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: 5555*

Host port on which to launch the Flower_ monitor.


.. _CRATE_DOCKER_GATE_BIOYODIE_RESOURCES_HOST_DIR:

CRATE_DOCKER_GATE_BIOYODIE_RESOURCES_HOST_DIR
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**No default. Must be set (even if to a dummy directory).**

A directory to be mounted that contains preprocessed UMLS data for the
Bio-YODIE NLP tool (which is part of KConnect/SemEHR, and which runs under
GATE). (You need to download UMLS data and use the
``crate_nlp_prepare_ymls_for_bioyodie`` script to process it. The output
directory used with that command is the directory you should specify here.)
On Windows, ensure this is within the Windows (not WSL2) file system.


.. _CRATE_DOCKER_GATE_VERSION:

CRATE_DOCKER_GATE_VERSION
^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: 9.0.1*

Version of GATE to be installed.


.. _CRATE_DOCKER_IMAGE_TAG:

CRATE_DOCKER_IMAGE_TAG
^^^^^^^^^^^^^^^^^^^^^^

*Defaults to the current CRATE version.*

Used to identify the version of the CRATE docker image.


CRATE_DOCKER_ODBC_USER_CONFIG
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: odbc_user.ini*

When using external databases with ODBC, this is the basename of the config file
that contains definitions of those databases. The ``ODBCINI`` environment variable
is set in the ``crate_server`` Docker container to point to this file. See (see
CRATE_DOCKER_CONFIG_HOST_DIR_)


.. _CRATE_DOCKER_INSTALL_GROUP_ID:

CRATE_DOCKER_INSTALL_GROUP_ID
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**No default. Must be set to the ID of a group on the host so that file systems can be shared.**
See CRATE_DOCKER_INSTALL_USER_ID_.


.. _CRATE_DOCKER_INSTALL_USER_ID:

CRATE_DOCKER_INSTALL_USER_ID
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**No default. Must be set to the ID of a user on the host so that file systems can be shared.**
See CRATE_DOCKER_INSTALL_GROUP_ID_


.. _CRATE_DOCKER_MY_CRATE_USER_NAME:

CRATE_DOCKER_REMOTE_PDB_CRATE_SERVER_HOST_PORT
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: 44444*

Used in development to debug the Python code in the ``crate_server`` Docker
container. Use ``breakpoint()`` in the code and then connect to this port on the
host: e.g. ``telnet 127.0.0.1 44444``.


CRATE_DOCKER_REMOTE_PDB_CRATE_WORKERS_HOST_PORT
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: 44445*

Used in development to debug the Python code in the ``crate_workers`` Docker
container. Use ``breakpoint()`` in the code and then connect to this port on the
host: e.g. ``telnet 127.0.0.1 44445``.


CRATE_DOCKER_REMOTE_PDB_CRATE_FLOWER_HOST_PORT
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: 44446*

Used in development to debug the Python code in the ``crate_flower`` Docker
container. Use ``breakpoint()`` in the code and then connect to this port on the
host: e.g. ``telnet 127.0.0.1 44446``.


CRATE_DOCKER_REMOTE_PDB_PORT
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: 44444*

Used in development to debug the Python code in the CRATE Docker
containers. This is the port used in the container itself.


CRATE_DOCKER_RESEARCH_DATABASE_NAME
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: research*

Name of the anonymised research database, either the demo one provided running
in a MySQL Docker container or your own.


CRATE_DOCKER_RESEARCH_DATABASE_USER_NAME
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: research*

Name of the database user used to access the anonymised research database,
either the demo one provided running in a MySQL Docker container or your own.


CRATE_DOCKER_RESEARCH_DATABASE_USER_PASSWORD
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: research*

Password of the database user used to access the anonymised research database,
either the demo one provided running in a MySQL Docker container or your own.


CRATE_DOCKER_RESEARCH_DATABASE_ROOT_PASSWORD
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: research*

This is the MySQL root password used only when creating the demo research
database.


CRATE_DOCKER_RESTART_POLICY
^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: always*

Determines how the CRATE Docker containers should handle an exit. See `Start
containers automatically`_ in the Docker Documentation for possible settings.


CRATE_DOCKER_SECRET_DATABASE_NAME
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: secret*

Name of the secret administrative database used by CRATE, either the demo
one provided running in a MySQL Docker container or your own.


CRATE_DOCKER_SECRET_DATABASE_USER_NAME
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: secret*

Name of the database user used to access CRATE's secret administrative database,
either the demo one provided running in a MySQL Docker container or your own.



CRATE_DOCKER_SECRET_DATABASE_USER_PASSWORD
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: secret*

Password of the database user used to access CRATE's secret administrative
database, either the demo one provided running in a MySQL Docker container or
your own.



CRATE_DOCKER_SECRET_DATABASE_ROOT_PASSWORD
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: secret*

This is the MySQL root password used only when creating the demo secret
administrative database.



CRATE_DOCKER_SOURCE_DATABASE_NAME
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: source*

Name of the source database to be anonymised by CRATE, either the demo one
provided running in a MySQL Docker container or your own.


CRATE_DOCKER_SOURCE_DATABASE_USER_NAME
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: source*

Name of the database user used to access the source database to be anonymised by
CRATE, either the demo one provided running in a MySQL Docker container or your
own.


CRATE_DOCKER_SOURCE_DATABASE_USER_PASSWORD
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: source*

Password of the database user used to access the source database to be
anonymised by CRATE, either the demo one provided running in a MySQL Docker
container or your own.



CRATE_DOCKER_SOURCE_DATABASE_ROOT_PASSWORD
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default: source*

This is the MySQL root password used only when creating the demo source database
to be anonymised by CRATE.


CRATE_DOCKER_STATIC_HOST_DIR
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Required by Docker. The installer will set this to* ``${CRATE_INSTALLER_CRATE_ROOT_HOST_DIR}/static``.

Space to collect files served statically by the CRATE web application (Django ``STATIC_ROOT``)


COMPOSE_PROJECT_NAME
^^^^^^^^^^^^^^^^^^^^

*Default: crate*

This is the Docker Compose project name. It's used as a prefix for all the
containers in this project.


.. _installer_environment_variables:

Installer Environment variables
-------------------------------

The Installer environment variables with prefix ``CRATE_INSTALLER`` are used by
the CRATE installer to write the various config files written by CRATE but not
needed by the running Docker instance. The installer will only prompt you for
information not set in these variables.


CRATE_INSTALLER_CRATE_DB_ENGINE
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The database engine used for the CRATE web application. This should be one of
``mssql``, ``mysql``, ``oracle`` or ``postgresql``.


CRATE_INSTALLER_CRATE_DB_PORT
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The port on the server hosting the CRATE web application database.


CRATE_INSTALLER_CRATE_DB_SERVER
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The name of the server hosting the CRATE web application database.



CRATE_INSTALLER_CRATE_ROOT_HOST_DIR
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The root directory under which all of the other CRATE files appear on the
host. For the hierarchy below, the root directory is ``/crate`` and the installer
will create the other directories underneath it if they are not already
present. This should be set either before running the installer or as
the ``--crate_root_dir`` argument to ``installer_boot.py``. The directory does not
have to exist but the user running the installer must have the correct
permissions for the installer to create both it and its subdirectories.

::

    /crate
    ├── bioyodie_resources
    ├── config
    ├── files
    ├── src
    ├── static
    └── venv

.. _CRATE_INSTALLER_CRATEWEB_SSL_CERTIFICATE:

CRATE_INSTALLER_CRATEWEB_SSL_CERTIFICATE
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default is blank.*

Filename for an SSL public certificate for accessing the CRATE web application
over HTTPS. See CRATE_DOCKER_CRATEWEB_HOST_PORT_ above.


.. _CRATE_INSTALLER_CRATEWEB_SSL_PRIVATE_KEY:

CRATE_INSTALLER_CRATEWEB_SSL_PRIVATE_KEY
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Default is blank.*

Filename for an SSL private key file for accessing the CRATE web application
over HTTPS. See CRATE_DOCKER_CRATEWEB_HOST_PORT_ above.


.. _CRATE_INSTALLER_CRATEWEB_USE_HTTPS:

CRATE_INSTALLER_CRATEWEB_USE_HTTPS
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Access the CRATE web app over HTTPS? (0 = no, 1 = yes)
See CRATE_DOCKER_CRATEWEB_HOST_PORT_ above.


CRATE_INSTALLER_CREATE_CRATE_DB_CONTAINER
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Use the provided MySQL database running under Docker for the CRATE web
application? (0 = no, 1 = yes).


CRATE_INSTALLER_CREATE_DEMO_DB_CONTAINERS
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Use the provided MySQL databases running under Docker, with fictitious data, to
demonstrate anonymisation? (0 = no, 1 = yes).


CRATE_INSTALLER_RESEARCH_DATABASE_ENGINE
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The database engine used for the anonymised research database. This should be one of
``mssql``, ``mysql``, ``oracle`` or ``postgresql``.


CRATE_INSTALLER_RESEARCH_DATABASE_HOST
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The name of the server hosting the anonymised research database.


CRATE_INSTALLER_RESEARCH_DATABASE_PORT
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The port on the server hosting the anonymised research database.



CRATE_INSTALLER_SECRET_DATABASE_ENGINE
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The database engine used for the CRATE's secret administrative database. This should be one of
``mssql``, ``mysql``, ``oracle`` or ``postgresql``.


CRATE_INSTALLER_SECRET_DATABASE_HOST
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The name of the server hosting CRATE's secret administrative database.


CRATE_INSTALLER_SECRET_DATABASE_PORT
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The port on the server hosting CRATE's secret administrative database.


CRATE_INSTALLER_SOURCE_DATABASE_ENGINE
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The database engine used for the source database to be anonymised by CRATE. This
should be one of ``mssql``, ``mysql``, ``oracle`` or ``postgresql``.


CRATE_INSTALLER_SOURCE_DATABASE_HOST
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The name of the server hosting the source database to be anonymised by CRATE.


CRATE_INSTALLER_SOURCE_DATABASE_PORT
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The port on the server hosting the source database to be anonymised by CRATE.



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

Shortcut for ``docker compose up -d`` with the relevant ``docker-compose-*.yaml`` files. The ``-d`` switch is short for
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


exec_crate_command
^^^^^^^^^^^^^^^^^^

Runs a command in the existing ``crate_server`` container.


Development notes
-----------------

- See https://camcops.readthedocs.io/en/latest/administrator/docker.html.
