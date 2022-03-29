..  crate_anon/docs/source/anonymisation/api.rst

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

.. _Django: https://www.djangoproject.com/


Using CRATE's anonymisation web server
--------------------------------------

.. _crate_anon_web_django_manage:

The CRATE anonymisation web front end uses Django_, which comes with a number of built-in
management comments. These can be run from within the CRATE virtual environment using:

.. code-block:: bash

    crate_anon_web_django_manage

The available commands are:

..  literalinclude:: _crate_anon_web_django_manage_help.txt
    :language: none


Anonymisation API documentation
-------------------------------

.. raw:: html
   :file: _crate_api.html
