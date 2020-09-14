..  crate_anon/docs/source/website_config/django_manage.rst

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


.. _Django: https://www.djangoproject.com/


.. _crate_django_manage:

Manage the CRATE web server
===========================

The CRATE web front end uses Django_, which comes with a number of built-in
management comments; to these, CRATE adds some more. All are available as
subcommands of

.. code-block:: bash

    crate_django_manage

The available commands are:

..  literalinclude:: _crate_django_manage_help.txt
    :language: none

Particularly relevant functions are as follows.

[auth]
------

changepassword
##############

Change a user's password from the command line.

..  literalinclude:: _crate_django_manage_changepassword_help.txt
    :language: none


createsuperuser
###############

Create a superuser from the command line.

..  literalinclude:: _crate_django_manage_createsuperuser_help.txt
    :language: none


[consent]
---------

fetch_optouts
#############

Show PIDs/MPIDs for patients who have opted out entirely from the anonymised
research database. See
:class:`crate_anon.crateweb.consent.management.commands.fetch_optouts.Command`.
This functionality is also available from the :ref`front-end web site, for
RDBMs <rdbm_view_optouts>`.

..  literalinclude:: _crate_django_manage_fetch_optouts_help.txt
    :language: none


lookup_consent
##############

Tests patient identity lookup from the command line, without saving anything.
See
:class:`crate_anon.crateweb.consent.management.commands.lookup_consent.Command`.
This functionality is also available from the :ref`front-end web site, for
developers <dev_lookup_consent_mode>`.

..  literalinclude:: _crate_django_manage_lookup_consent_help.txt
    :language: none


lookup_patient
##############

Tests patient identity lookup from the command line, without saving anything.
See
:class:`crate_anon.crateweb.consent.management.commands.lookup_patient.Command`.
This functionality is also available from the :ref`front-end web site, for
developers <dev_lookup_patient>`.

..  literalinclude:: _crate_django_manage_lookup_patient_help.txt
    :language: none


populate
########

Ensures the database has entries for all the master leaflets used by CRATE.
(Will not destroy any existing leaflet records.)

See

- :class:`crate_anon.crateweb.consent.management.commands.populate.Command`
- :meth:`crate_anon.crateweb.consent.models.Leaflet.populate`

..  literalinclude:: _crate_django_manage_populate_help.txt
    :language: none


resubmit_unprocessed_tasks
##########################

Ask Celery to catch up on any unprocessed CRATE tasks. Use this with caution!
See :func:`crate_anon.crateweb.consent.tasks.resubmit_unprocessed_tasks_task`.

..  literalinclude:: _crate_django_manage_resubmit_unprocessed_tasks_help.txt
    :language: none


test_email
##########

Tests the backend and e-mail systems by sending an e-mail to the RDBM. Also
available from the :ref:`front-end web site <rdbm_test_message_queue>`.

..  literalinclude:: _crate_django_manage_test_email_help.txt
    :language: none


.. _django_manage_email_rdbm:

email_rdbm
##########

E-mails the RDBM.

..  literalinclude:: _crate_django_manage_email_rdbm_help.txt
    :language: none


[core]
------

.. _django_manage_runcpserver:

runcpserver
###########

Launches the CherryPy web server.

..  literalinclude:: _crate_django_manage_runcpserver_help.txt
    :language: none


[staticfiles]
-------------

collectstatic
#############

Copy relevant static files from their source location to the place that CRATE
will serve them to users (or another front-end server, like Apache, will on its
behalf). Needs to be run as part of site setup.

..  literalinclude:: _crate_django_manage_collectstatic_help.txt
    :language: none


.. _django_manage_runserver:

runserver
#########

Launches the Django test web server.

..  literalinclude:: _crate_django_manage_runserver_help.txt
    :language: none
