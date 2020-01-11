.. crate_anon/docs/source/website_using/developer_admin.rst

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

Developer functions
-------------------

Additional testing functions are provided for those superusers who have the
"developer" flag set. They allow breaking of the usual restrictions on the
RDBM, and should be used for authorized testing (generally on systems with
fictional data) only.


Developer admin site
~~~~~~~~~~~~~~~~~~~~

This Django admin site allows you full control over all models used by the
site. In addition to the objects managed by the :ref:`RDBM admin site
<rdbm_admin_site>`, this includes:

- Clinician responses:
  :class:`crate_anon.crateweb.consent.models.ClinicianResponse`
- Dummy patient source information:
  :class:`crate_anon.crateweb.consent.models.DummyPatientSourceInfo`
- Patient lookups:
  :class:`crate_anon.crateweb.consent.models.PatientLookup`

Some additional permissions are also added for the other models.

The developer views are those ending in ``DevAdmin`` within
:mod:`crate_anon.crateweb.core.admin`.


Generate random NHS numbers for testing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Self-explanatory. All are completely random (so there is a risk of generating a
real one!) and pass the NHS number checksum system.


.. _dev_lookup_patient:

Test patient lookup without saving data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This function takes an NHS number and looks up (identifiable) patient details
without saving anything. Use it to test the identity lookup system.


.. _dev_lookup_consent_mode:

Test consent mode lookup without saving data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This function takes an NHS number and looks up CRATE traffic-light (etc.)
consent mode information, without saving anything. Use it to test the consent
mode lookup system.


Test templates
~~~~~~~~~~~~~~

This section offers all the templates used by the consent-to-contact system
(most in HTML and PDF versions), using a specific fictional patient, study,
researcher, and clinician (ID number -1).

The templates vary by patient age, consent mode, and so on. You can therefore
view variants by altering the default URLs to use these URL query parameters:

- ``age=<age_years>``
- ``age_months=<age_months>``
- ``consent_mode=<value>``; for the consent mode, specify ``red``, ``yellow``,
  ``green``, or anything else for ``None``
- ``request_direct_approach=<value>`` (use 0 or 1)
- ``consent_after_discharge=<value>`` (use 0 or 1)

An example is therefore
``?age=40;age_months=2;consent_mode=yellow;request_direct_approach=1;consent_after_discharge=0``.

The fictional patient's DOB is synthesized from the age you specify and today's
date.

See :func:`crate_anon.crateweb.consent.models.make_dummy_objects` for defaults.
