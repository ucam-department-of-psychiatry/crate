.. crate_anon/docs/source/website_config/web_config_file.rst

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

.. _web_config_file:

Web config file
===============

Specimen config file
--------------------

To obtain a specimen file, use

.. code-block:: none

    crate_print_demo_crateweb_config

Specimen web config as of 2017-02-28:

..  literalinclude:: specimen_web_config.py
    :language: python


Django secret key
-----------------

Use this command to generate a new random secret key:

.. code-block:: bash

    crate_generate_new_django_secret_key

You can use the output for the `SECRET_KEY` variable in the config file.
