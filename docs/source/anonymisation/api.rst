..  crate_anon/docs/source/anonymisation/api.rst

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

.. _Django: https://www.djangoproject.com/
.. _Django Rest Framework: https://www.django-rest-framework.org

.. _anonymisation_api:

============================================
 Using CRATE's anonymisation API web server
============================================

The CRATE anonymisation API uses Django_, with `Django Rest Framework`_. To
create the secrets required by Django:

.. code-block:: none

    crate_anon_web_create_private_settings

Next, to set up the SQLite database:

.. code-block:: none

    crate_anon_web_django_manage migrate

Create the superuser:

.. code-block:: none

    crate_anon_web_django_manage createsuperuser


Create any private settings required by the Django app such as the Django secret key:

.. _crate_anon_web_create_private_settings:

.. code-block:: none

    crate_anon_web_create_private_settings


.. _crate_anon_web_django_manage:

The CRATE anonymisation web front end uses Django_, which comes with a number of built-in
management comments. These can be run from within the CRATE virtual environment using:

.. code-block:: bash

    crate_anon_web_django_manage

The available commands are:

..  literalinclude:: _crate_anon_web_django_manage_help.txt
    :language: none


=================================
 Anonymisation API documentation
=================================

.. raw:: html
   :file: _crate_api.html
