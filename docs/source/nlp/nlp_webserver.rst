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

.. _nlp_webserver:

NLPRP web server
----------------

crate_nlp_webserver_initialize_db
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: crate_nlp_webserver_initialize_db_help.txt
    :language: none


crate_nlp_webserver_print_demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Prints a demo NLP web server config.

.. literalinclude:: crate_nlp_webserver_print_demo_help.txt
    :language: none

Config specimen:

.. literalinclude:: nlp_webserver_demo_config.ini
    :language: ini

Processors specimen:

.. literalinclude:: nlp_webserver_demo_processors.py
    :language: python


crate_nlp_webserver_manage_users
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: crate_nlp_webserver_manage_users_help.txt
    :language: none


crate_nlp_webserver_generate_encryption_key
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Generates a random encryption key and prints it to the screen.



.. _Redis: https://redis.io

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

