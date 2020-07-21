..  docs/source/administrator/docker.rst

..  Copyright (C) 2012-2020 Rudolf Cardinal (rudolf@pobox.com).
    .
    This file is part of CamCOPS.
    .
    CamCOPS is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    .
    CamCOPS is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.
    .
    You should have received a copy of the GNU General Public License
    along with CamCOPS. If not, see <http://www.gnu.org/licenses/>.

.. _AMQP: https://en.wikipedia.org/wiki/Advanced_Message_Queuing_Protocol
.. _Docker: https://www.docker.com/
.. _Docker Compose: https://docs.docker.com/compose/
.. _Flower: https://flower.readthedocs.io/
.. _Gunicorn: https://gunicorn.org/
.. _MySQL: https://www.mysql.com/
.. _mysqlclient: https://pypi.org/project/mysqlclient/
.. _RabbitMQ: https://www.rabbitmq.com/


.. _server_docker:

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
- the CamCOPS web server itself, offering SSL directly via Gunicorn_ on Linux
  (``camcops_server``);
- the CamCOPS scheduler (``camcops_scheduler``);
- CamCOPS workers, to perform background tasks (``camcops_workers``);
- a background task monitor, using Flower_ (``camcops_monitor``).


Quick start
-----------

#.  Ensure you have Docker and Docker Compose installed (see
    :ref:`prerequisites <docker_prerequisites>`).

#.  Obtain the CamCOPS source code.

    .. todo::
        Docker/CamCOPS source: (a) is that the right method? Or should we be
        using ``docker-app``? (Is that experimental?) (b) Document.

#.  Set the :ref:`environment variables <docker_environment_variables>`
    required for Docker operation. (You probably want to automate this with a
    script.)

#.  Change to the ``server/docker/linux`` directory within the CamCOPS source
    tree.

    .. note::
        If you are using a Windows host, change to ``server/docker/windows``
        instead, and for all the commands below, instead of ``./some_command``,
        run ``some_command.bat``.

#.  Start the containers with:

    .. code-block:: bash

        ./start_camcops_docker_interactive

    This gives you an interactive view. As this is the first run, it will also
    create containers, volumes, the database, and so on. It will then encounter
    errors (e.g. config file not specified properly, or the database doesn't
    have the right structure), and will stop.

#.  Run this command to create a demonstration config file with the standard
    name:

    .. code-block:: bash

        ./print_demo_camcops_config > "${CAMCOPS_DOCKER_CONFIG_HOST_DIR}/camcops.conf"

#.  Edit that config file. See :ref:`here <server_config_file>` for a full
    description and :ref:`here <camcops_config_file_docker>` for special Docker
    requirements.

#.  Create the database structure (tables):

    .. code-block:: bash

        ./upgrade_db

#.  Create a superuser:

    .. code-block:: bash

        ./camcops_server make_superuser

#.  Time to test! Restart with

    .. code-block:: bash

        ./start_camcops_docker_interactive

    Everything should now be operational. Using any web browser, you should be
    able to browse to the CamCOPS site at your chosen host port and protocol,
    and log in using the account you have just created.

#.  When you're satisfied everything is working well, you can stop interactive
    mode (CTRL-C) and instead use

    .. code-block:: bash

        ./start_camcops_docker_detached

    which will fire up the containers in the background. To take them down
    again, use

    .. code-block:: bash

        ./stop_camcops_docker

You should now be operational! If Docker is running as a service on your
machine, CamCOPS should also be automatically restarted by Docker on reboot.


.. _docker_prerequisites:

Prerequisites
-------------

You can run Docker on several operating systems. For example, you can run
Docker under Linux (and CamCOPS will run in Linux-under-Docker-under-Linux).
You can similarly run Docker under Windows (and CamCOPS will run in
Linux-under-Docker-under-Windows).

- You need Docker Engine installed. See
  https://docs.docker.com/engine/install/.

- You need Docker Compose installed. See
  https://docs.docker.com/compose/install/.


.. _docker_environment_variables:

Environment variables
---------------------

Docker control files are in the ``server/docker`` directory of the CamCOPS
source tree. Setup is controlled by the ``docker-compose`` application.

.. note::

    Default values are taken from ``server/docker/.env``. Unfortunately, this
    name is fixed by Docker Compose, and this file is hidden under Linux (as
    are any files starting with ``.``).


.. _CAMCOPS_DOCKER_CONFIG_HOST_DIR:

CAMCOPS_DOCKER_CONFIG_HOST_DIR
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**No default. Must be set.**

Path to a directory on the host that contains key configuration files. Don't
use a trailing slash.

In this directory, there should be a file called ``camcops.conf``, the config
file (or, if you have set CAMCOPS_DOCKER_CAMCOPS_CONFIG_FILENAME_, that
filename!).

.. note::
    **Under Windows,** don't use Windows paths like
    ``C:\Users\myuser\my_camcops_dir``. Translate this to Docker notation as
    ``/host_mnt/c/Users/myuser/my_camcops_dir``. As of 2020-07-21, this doesn't
    seem easy to find in the Docker docs!


.. _CAMCOPS_DOCKER_CAMCOPS_CONFIG_FILENAME:

CAMCOPS_DOCKER_CAMCOPS_CONFIG_FILENAME
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Default: camcops.conf*

Base name of the CamCOPS config file (see CAMCOPS_DOCKER_CONFIG_HOST_DIR_).


CAMCOPS_DOCKER_FLOWER_HOST_PORT
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Default: 5555*

Host port on which to launch the Flower_ monitor.


CAMCOPS_DOCKER_CAMCOPS_HOST_PORT
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Default: 443*

The TCP/IP port number on the host computer that CamCOPS should provide an
HTTP or HTTPS (SSL) connection on.

It is strongly recommended that you run CamCOPS over HTTPS. The two ways of
doing this are:

- Have CamCOPS run plain HTTP, and connect it to another web server (e.g.
  Apache) that provides the HTTPS component.

  - If you do this, you should **not** expose this port to the "world", since
    it offers insecure HTTP.

  - The motivation for this method is usually that you are running multiple web
    services, of which CamCOPS is one.

  - We don't provide Apache within Docker, because the Apache-inside-Docker
    would only see CamCOPS, so there's not much point -- you might as well
    use the next option...

- Have CamCOPS run HTTPS directly, by specifying the :ref:`SSL_CERTIFICATE
  <SSL_CERTIFICATE>` and :ref:`SSL_PRIVATE_KEY <SSL_PRIVATE_KEY>` options.

  - This is simpler if CamCOPS is the only web service you are running on this
    machine. Use the standard HTTPS port, 443, and expose it to the outside
    through your server's firewall. (You are running a firewall, right?)


CAMCOPS_DOCKER_CAMCOPS_INTERNAL_PORT
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Default: 8000*

The TCP/IP port number used by CamCOPS internally. Must match the :ref:`PORT
<PORT>` option in the CamCOPS config file.


.. _CAMCOPS_DOCKER_MYSQL_CAMCOPS_DATABASE_NAME:

CAMCOPS_DOCKER_MYSQL_CAMCOPS_DATABASE_NAME
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Default: camcops*

Name of the MySQL database to be used for CamCOPS data.


.. _CAMCOPS_DOCKER_MYSQL_CAMCOPS_USER_PASSWORD:

CAMCOPS_DOCKER_MYSQL_CAMCOPS_USER_PASSWORD
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**No default. Must be set during MySQL container creation.**

MySQL password for the CamCOPS database user (whose name is set by
CAMCOPS_DOCKER_MYSQL_CAMCOPS_USER_NAME_).

.. note::
    This only needs to be set when Docker Compose is creating the MySQL
    container for the first time. After that, it doesn't have to be set (and is
    probably best not set for security reasons!).


.. _CAMCOPS_DOCKER_MYSQL_CAMCOPS_USER_NAME:

CAMCOPS_DOCKER_MYSQL_CAMCOPS_USER_NAME
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Default: camcops*

MySQL username for the main CamCOPS user. This user is given full control over
the database named in CAMCOPS_DOCKER_MYSQL_CAMCOPS_DATABASE_NAME_. See also
CAMCOPS_DOCKER_MYSQL_CAMCOPS_USER_PASSWORD_.


CAMCOPS_DOCKER_MYSQL_HOST_PORT
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Default: 3306*

Port published to the host, giving access to the CamCOPS MySQL installation.
You can use this to allow other software to connect to the CamCOPS database
directly.

This might include using MySQL tools from the host to perform database backups
(though Docker volumes can also be backed up in their own right).

The default MySQL port is 3306. If you run MySQL on your host computer for
other reasons, this port will be taken, and you should change it to something
else.

You should **not** expose this port to the "outside", beyond your host.


.. _CAMCOPS_DOCKER_MYSQL_ROOT_PASSWORD:

CAMCOPS_DOCKER_MYSQL_ROOT_PASSWORD
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**No default. Must be set during MySQL container creation.**

MySQL password for the ``root`` user.

.. note::
    This only needs to be set when Docker Compose is creating the MySQL
    container for the first time. After that, it doesn't have to be set (and is
    probably best not set for security reasons!).


COMPOSE_PROJECT_NAME
~~~~~~~~~~~~~~~~~~~~

*Default: camcops*

This is the Docker Compose project name. It's used as a prefix for all the
containers in this project.


.. _camcops_config_file_docker:

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

All live in the ``server/docker`` directory.


bash_within_docker
~~~~~~~~~~~~~~~~~~

Runs a Bash shell within the ``camcops_workers`` container.

.. warning::

    Running a shell within a container allows you to break things! Be careful.


camcops_server
~~~~~~~~~~~~~~

This script runs the ``camcops_server`` command within the Docker container.
For example:

    .. code-block:: bash

        ./camcops_server --help


.. _docker_print_demo_camcops_config:

print_demo_camcops_config
~~~~~~~~~~~~~~~~~~~~~~~~~

Prints a demonstration CamCOPS config file with Docker options set. Save the
output as demonstrated above.


start_camcops_docker_detached
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Shortcut for ``docker-compose up -d``. The ``-d`` switch is short for
``--detach`` (or daemon mode).


start_camcops_docker_interactive
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Shortcut for ``docker-compose up --abort-on-container-exit``.

.. note::
    The ``docker-compose`` command looks for a Docker Compose configuration
    file with a default filename; one called ``docker-compose.yaml`` is
    provided.


stop_camcops_docker
~~~~~~~~~~~~~~~~~~~

Shortcut for ``docker-compose down``.


.. _server_docker_upgrade_db:

upgrade_db
~~~~~~~~~~

This script upgrades the CamCOPS database to the current version.

- The database is specified by the DB_URL parameter in the CamCOPS config file.
  See :ref:`above <camcops_config_file_docker>`.

- The config file is found by Docker according to the
  CAMCOPS_DOCKER_CONFIG_HOST_DIR_ and CAMCOPS_DOCKER_CAMCOPS_CONFIG_FILENAME_
  environment variables (q.v.).


venv_within_docker
~~~~~~~~~~~~~~~~~~

Launches a shell within the ``camcops_workers`` container, and activates the
CamCOPS Python virtual environment too.


within_docker
~~~~~~~~~~~~~

This script runs a command within the ``camcops_workers`` container. For
example, to explore this container, you can do

    .. code-block:: bash

        ./within_docker /bin/bash

... which is equivalent to the ``bash_within_docker`` script (see above and
note the warning).


Development notes
-----------------

- **Config information.**
  There are several ways, but mounting a host directory containing a config
  file is perfectly reasonable. See
  https://dantehranian.wordpress.com/2015/03/25/how-should-i-get-application-configuration-into-my-docker-containers/.

- **Secrets, such as passwords.**
  This is a little tricky. Environment variables and config files are both
  reasonable options; see e.g.
  https://stackoverflow.com/questions/22651647/docker-and-securing-passwords.
  Environment variables are visible externally (e.g. ``docker exec CONTAINER
  env``) but you have to have Docker privileges (be in the ``docker`` group) to
  do that. Docker "secrets" require Docker Swarm (not just plain Docker
  Compose). We are using a config file for CamCOPS, and environment variables
  for the MySQL container.

- **Data storage.**
  Should data (e.g. MySQL databases) be stored on the host (via a "bind mount"
  of a directory), or in Docker volumes? Docker says clearly: volumes. See
  https://docs.docker.com/storage/volumes/.

- **TCP versus UDS.**
  Currently the connection between CamCOPS and MySQL is via TCP/IP. It would be
  possible to use Unix domain sockets instead. This would be a bit trickier.
  Ordinarily, it would bring some speed advantages; I'm not sure if that
  remains the case between Docker containers. The method is to mount a host
  directory; see
  https://superuser.com/questions/1411402/how-to-expose-linux-socket-file-from-docker-container-mysql-mariadb-etc-to.
  It would add complexity. The other advantage of using TCP is that we can
  expose the MySQL port to the host for administrative use.

- **Database creation.**
  It might be nice to upgrade the database a little more automatically, but
  this is certainly not part of Docker *image* creation (the image is static
  and the data is dynamic) and shouldn't be part of routine container startup,
  so perhaps it's as good as is reasonable.

- **Scaling up.**
  At present we use a fixed number of containers, some with several processes
  running within. There are other load distribution mechanisms possible with
  Docker Compose.


===============================================================================

.. rubric:: Footnotes

.. [#host]
    https://nickjanetakis.com/blog/docker-tip-54-fixing-connection-reset-by-peer-or-similar-errors
