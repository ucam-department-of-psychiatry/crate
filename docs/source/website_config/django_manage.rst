.. crate_anon/docs/source/website_config/django_manage.rst

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


.. _Django: https://www.djangoproject.com/


.. _crate_django_manage:

Manage the CRATE web server
===========================

The CRATE web front end uses Django_, which comes with a number of built-in
management comments; to these, CRATE adds some more. All are available as
subcommands of

.. code-block:: bash

    crate_django_manage

As of 2018-06-29, the available commands are:

..  literalinclude:: crate_django_manage_help.txt
    :language: none
