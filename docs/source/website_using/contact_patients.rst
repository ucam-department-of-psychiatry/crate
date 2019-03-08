.. crate_anon/docs/source/website_using/contact_patients.rst

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


Contacting patients about research studies
------------------------------------------

This part of CRATE implements the consent-for-contact traffic light system
described in the :ref:`overview <overview>`.

The principle is that researchers are only given information that will identify
a patient with that patient's explicit consent.


.. _c4c_view_manage_studies:

View/manage your studies
~~~~~~~~~~~~~~~~~~~~~~~~

This section is a Django_ admin site that allows researchers to enter details
of their studies and associated information.

.. todo:: Write more on researcher admin views of studies.


.. _c4c_submit_contact_request:

Submit a contact request
~~~~~~~~~~~~~~~~~~~~~~~~

Suppose you're running an approved study and have found patients in the
de-identified database. You'd like to meet them. You know their :ref:`research
IDs <rid>`, but you don't know who they are. Do they want you to contact them
to offer them potential participation?

Researchers can submit contact requests based on :ref:`RID <rid>` or :ref:`MRID
<mrid>`.

Database administrators (:ref:`RDBMs <rdbm>`) may also look up using
identifiable information such as the :ref:`MPID <mpid>`.

Clinicians have an additional :ref:`privileged contact request
<clinician_privileged_submit_contact_request>` option.
