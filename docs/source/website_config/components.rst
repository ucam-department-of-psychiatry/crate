..  crate_anon/docs/source/website_config/components.rst

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
.. _Apache: http://httpd.apache.org/
.. _Celery: http://www.celeryproject.org/
.. _CherryPy: https://cherrypy.org/
.. _Django: https://www.djangoproject.com/
.. _Flower: http://flower.readthedocs.io/
.. _Gunicorn: http://gunicorn.org/
.. _MySQL: http://www.mysql.com/
.. _RabbitMQ: https://www.rabbitmq.com/
.. _SQL Server: https://en.wikipedia.org/wiki/Microsoft_SQL_Server
.. _supervisor: http://supervisord.org/
.. _WSGI: https://en.wikipedia.org/wiki/Web_Server_Gateway_Interface


Web site components
===================

- A **front-end web server** such as Apache_ runs on your server and talks to
  the world. It serves static files and may run other web sites, but it routes
  a subset of its traffic to an internal TCP/IP port, where it finds CRATE.

- **CRATE** runs and serves content to an internal TCP/IP port.

  - CRATE implements its web front end via Django_ (which provides a WSGI_
    application) and a "mini" web server like CherryPy_ or Gunicorn_
    [#gunicornunixonly]_ (which makes that WSGI application talk to TCP/IP).

- CRATE talks to one or more **databases** (e.g. MySQL_, `SQL Server`_). These
  include research databases, but also a database used by CRATE to store its
  own data.

- A separate CRATE subsystem handles **back-end tasks**, like sending e-mails
  and processing consent requests (which can be a bit slow).

  - This uses the Celery_ task queue system. Celery itself is a Python program
    that talks to a message queue, and can put messages into this queue (CRATE
    calls Celery) [#cratetocelery]_, or retrieve them from the queue (Celery
    calls CRATE) [#celeryentrypoint]_ to get jobs done.

  - The actual message queue is managed by a "message broker", which is
    software that provides message queues via AMQP_; typically this broker is
    RabbitMQ_.

  - You can use Flower_ to monitor this system (see
    :ref:`crate_launch_flower`).

- Some sort of **operating system supervisor** typically controls the various
  aspects of CRATE. Under Windows, CRATE provides a Windows service (see
  :ref:`windows_service`). Under Linux, supervisor_ is typically used.



===============================================================================

.. rubric:: Footnotes

.. [#gunicornunixonly] Gunicorn_ runs under Windows only

.. [#cratetocelery] In the source code, look for calls like
   ``email_rdbm_task.delay()``.

.. [#celeryentrypoint] See ``crate_anon/crateweb/consent/celery.py``.
