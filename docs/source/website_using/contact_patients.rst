..  crate_anon/docs/source/website_using/contact_patients.rst

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


Contact requests
^^^^^^^^^^^^^^^^


Here, you can view and filter your contact requests and their progress (showing
the aspects that you're allowed to see) [#researchercrclass]_.

You can also :ref:`submit a contact request <c4c_submit_contact_request>`.

Clinicians will be able to respond in one of the following ways, with the
coresponding code letter:

R: Clinician asks RDBM to pass request to patient
A: Clinician will pass the request to the patient
B: Clinician vetoes on clinical grounds
C: Patient is definitely ineligible
D: Patient is dead/discharged or details are defunct

As of CRATE version 0.18.94, option C will always be available to the
clinician.


Emails
^^^^^^


Here, you can view e-mails sent by the system to which you have access
[#researcheremailclass]_. (You won't be able to see others, like e-mails sent
to clinicians about patients you might wish to identify.)


Leaflets
^^^^^^^^


Here, you can view leaflets associated with the system as a whole
[#researcherleafletclass]_.


Letters
^^^^^^^


Here, you can view letters that the system has generated electronically and
send to you or your team, if you have permission [#researcherletterclass]_.


Studies
^^^^^^^


Here, you can view studies with which you are associated
[#researcherstudyclass]_. The RDBM can edit these for you.


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


===============================================================================

.. rubric:: Footnotes

.. [#researchercrclass]
    In the code, this is :class:`crate_anon.crateweb.core.admin.EmailResAdmin`.

.. [#researcheremailclass]
    In the code, this is
    :class:`crate_anon.crateweb.core.admin.ContactRequestResAdmin`.

.. [#researcherleafletclass]
    In the code, this is
    :class:`crate_anon.crateweb.core.admin.LeafletResAdmin`.

.. [#researcherstudyclass]
    In the code, this is :class:`crate_anon.crateweb.core.admin.StudyResAdmin`.

.. [#researcherletterclass]
    In the code, this is
    :class:`crate_anon.crateweb.core.admin.LetterResAdmin`.


