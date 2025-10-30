..  crate_anon/docs/source/misc/tcpip_ports.rst

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
.. _Flower: http://flower.readthedocs.io/
.. _Microsoft SQL Server: https://www.microsoft.com/en-us/sql-server
.. _MySQL: https://www.mysql.com/
.. _PostgreSQL: https://www.postgresql.org/
.. _RabbitMQ: https://www.rabbitmq.com/


.. _tcpip_ports:

Common relevant TCP/IP ports
----------------------------


... plus some that are less relevant here.

======= =======================================================================
Port    Default function
======= =======================================================================
22      SSH
25      SMTP
80      HTTP
443     HTTPS
465     SMTPS: secure SMTP (implicit TLS for SMTP)
587     MSA; e.g. explicit TLS (via STARTTLS command) for SMTP
1433    `Microsoft SQL Server`_
2575    MLLP/HL7
3306    MySQL_
5432    PostgreSQL_
5555    Default internal port for Flower_
5672    AMQP_ (e.g. RabbitMQ_)
8443    Relatively common alternative for HTTPS (e.g. for testing)
15672   Default internal port for RabbitMQ_ admin interface
======= =======================================================================
