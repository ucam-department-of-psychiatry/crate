..  crate_anon/docs/source/website_config/launch_celery.rst

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
.. _Celery: http://www.celeryproject.org/
.. _Flower: http://flower.readthedocs.io/
.. _RabbitMQ: https://www.rabbitmq.com/


Launch Celery
=============

When web sites want to do something slow, or spontaneously, they should not do
so within a user interaction. If the user says "build me a 1 Gb file for
download", the web site shouldn't build it and then provide it for download;
the user will think the site is unresponsive. Usually, it should reply
immediately to say "OK, working on that", do the work, and then indicate to the
user somehow that the job is done. Similarly, web sites may need to act
spontaneously (e.g. do things at midnight every day).

The general method of doing this is to have a task queue. CRATE uses Celery_
for its task queue. It creates Celery tasks when it wants to do something slow
(like checking consent modes and sending a bunch of e-mails).

In turn, Celery puts tasks into a message queue system, passing messages via
the AMQP_ protocol. By default, the message broker is RabbitMQ_. It's the job
of the broker to receive messages, keep them safe (so that they're not lost if
the system is rebooted, for example), and to make them available to software
that needs them.

When a task is run, Celery will call back into the CRATE code to get the job
done, but using a different process from the one that responded to the user's
initial HTTP request.


.. _crate_launch_celery:

crate_launch_celery
-------------------

This launches the CRATE Celery system. You need this to be running for CRATE
to work properly. (See also :ref:`Windows service <windows_service>`.)

Options:

..  literalinclude:: crate_launch_celery_help.txt
    :language: none


.. _crate_celery_status:

crate_celery_status
-------------------

This executes the command ``celery -A crate_anon.crateweb.consent status``.


.. _crate_launch_flower:

crate_launch_flower
-------------------

This command has no options. It launches the Celery Flower_ tool, which is for
monitoring Celery, and associates it with the CRATE NLP web server. It starts a
local web server (by default on port 5555; see :ref:`TCP/IP ports
<tcpip_ports>`); if you browse to http://localhost:5555/ or
http://127.0.0.1:5555/, you can monitor what's happening.


See also
--------

If Celery jobs are taken out of the queue and then crash inside CRATE, you may
wish to resubmit unprocessed work. For this, use

.. code-block:: bash

    crate_django_manage resubmit_unprocessed_tasks

See :ref:`crate_django_manage <crate_django_manage>`.
