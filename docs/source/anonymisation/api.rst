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


Using CRATE's anonymisation API web server
------------------------------------------


The CRATE anonymisation API uses the CRATE web interface. See :ref:`Configuring
the CRATE web interface <configuring_the_crate_web_interface>` and :ref:`Using
the CRATE web interface <using_the_crate_web_interface>`.

You can access the anonymisation API menu at ``/anon_api/``. You do not need to
be logged in.

The API endpoint is at ``/anon_api/scrub/``


Anonymisation API documentation
-------------------------------


.. raw:: html
   :file: _crate_api.html
