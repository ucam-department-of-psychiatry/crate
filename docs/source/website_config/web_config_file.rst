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

.. _pdfkit: https://pypi.org/project/pdfkit/
.. _wkhtmltopdf: https://wkhtmltopdf.org/


.. _web_config_file:

Web config file
===============

..  contents::
    :local:
    :depth: 2


General
-------

Defaults are in :mod:`crate_anon.crateweb.config.settings`, which are then
overridden as required by your site's Python config file (in standard Django
fashion). The "normal" settings to consider are described below.


Site URL configuration
----------------------

DJANGO_SITE_ROOT_ABSOLUTE_URL
#############################

``type: str``

Absolute root URL of the site (e.g. ``https://mymachine.mydomain`` for hosting
under Apache). Don't add a trailing slash.


FORCE_SCRIPT_NAME
#################

``type: str``

Script name to enforce, e.g. ``/crate`` for a site being hosted at a non-root
location such as ``https://mymachine.mydomain/crate``.


Site security
-------------

See also the site security deployment checklist at
https://docs.djangoproject.com/en/1.8/howto/deployment/checklist/.


SECRET_KEY
##########

``type: str``

Secret key used for the site.

This is a Django setting: see
https://docs.djangoproject.com/en/2.2/ref/settings/#std:setting-SECRET_KEY.

Use this command to generate a new random secret key:

.. _crate_generate_new_django_secret_key:

.. code-block:: bash

    crate_generate_new_django_secret_key


DEBUG
#####

``type: bool``

Turn on debugging features? **Do not use this for production sites.**

This is a Django setting:
https://docs.djangoproject.com/en/2.2/ref/settings/#debug.

Debug features by default include:

- allowing any site to connect, via ``ALLOWED_HOSTS``;
- turning on the Django Debug Toolbar, via ``DEBUG_TOOLBAR_CONFIG`` (see
  https://django-debug-toolbar.readthedocs.io/en/latest/configuration.html)

**Note** that when you set ``DEBUG = False``, as you should, you must ensure
that static files are served properly.


ALLOWED_HOSTS
#############

This is a Django setting; see
https://docs.djangoproject.com/en/2.2/ref/settings/#std:setting-ALLOWED_HOSTS.


Celery configuration
--------------------

BROKER_URL
##########

``type: str``

Optionally, this can be overridden. By default, it is ``amqp://``.

- Overriding ``BROKER_URL`` will allow you to use multiple virtual hosts, to
  host multiple independent instances of CRATE (in the unlikely event you'd
  want to!). See
  http://stackoverflow.com/questions/12209652/multi-celery-projects-with-same-rabbitmq-broker-backend-process
- Similarly, override ``BROKER_URL`` to improve RabbitMQ security.


CELERYBEAT_SCHEDULE
###################

Schedule back-end (Celery) tasks for specific times. See:

- Celery periodic tasks:
  https://docs.celeryproject.org/en/latest/userguide/periodic-tasks.html
- Celery ``beat_schedule`` setting:
  https://docs.celeryproject.org/en/latest/userguide/configuration.html
- Via Django:
  https://stackoverflow.com/questions/37848481/how-to-configure-celerybeat-schedule-in-django-settings/37851090
- Renaming from ``CELERYBEAT_SCHEDULE`` to ``beat_schedule`` (and from
  ``BROKER_URL`` to ``broker_url`` from Celery version 4.0, with backwards
  compatibility):
  https://docs.celeryproject.org/en/latest/userguide/configuration.html#new-lowercase-settings

The typical use is to make CRATE check the primary clinical record regularly --
so that, for example, if a patient withdraws their consent, this is processed
promptly to create a withdrawal-of-consent letter to relevant researchers. Like
this:

.. code-block:: python

    from celery.schedules import crontab

    # ...

    CELERYBEAT_SCHEDULE = {
        'refresh_consent_modes_at_midnight': {
            'task': 'crate_anon.crateweb.consent.tasks.refresh_all_consent_modes',
            'schedule': crontab(minute=0, hour=0),
        },
    }

.. note::

    The scheduled tasks will not run unless you start Celery with the beat
    option - i.e. run ``crate_launch_celery --command=beat``. This is
    done automatically as part of the Windows service launcher.

Celery picks up these definitions as follows:

- ``crate_anon/crateweb/consent/celery.py`` sets the environment variable
  ``DJANGO_SETTINGS_MODULE``, then calls
  ``app.config_from_object('django.conf:settings')``. That loads
  ``django.conf`` and reads its ``settings`` (which loads the user's Django
  configuration file).


Database configuration
----------------------

.. _DATABASES:

DATABASES
#########

This is a Django setting:
https://docs.djangoproject.com/en/2.2/ref/settings/#std:setting-DATABASES.

You require databases with the following names:

- ``default``: the main database used by CRATE to store its information (e.g.
  users, studies, queries via the web site);
- ``research``: the anonymised research database itself;
- optionally, one or more secret databases for RID/PID mapping,
  cross-referenced by RESEARCH_DB_INFO below;
- optionally, one or more specific databases representing a copy of a primary
  clinical records system; their names must be one of those in
  :data:`crate_anon.crateweb.config.constants.ClinicalDatabaseType.DATABASE_CHOICES`.

.. warning::

    It is critically important that the connection information you give for the
    ``research`` database (i.e. its user's access) is read-only for the
    research databases [1] and has no access whatsoever to secret databases
    (like the ``default`` or "secret" databases) [2]. Researchers are given
    full ability to execute sql via this connection, and can do so for any
    databases that the connection permits, not just the one you specify
    explicitly.

    [1] So researchers can't alter/delete research data.

    [2] So researchers can't see secrets.


CLINICAL_LOOKUP_DB
##################

``type: str``

Which database (from DATABASES_) should be used to look up demographic details?

It must be

- one named in
  :data:`crate_anon.crateweb.config.constants.ClinicalDatabaseType.DATABASE_CHOICES`;
- defined in DATABASES_, unless it is ``dummy_clinical``, which is just for
  testing purposes.


CLINICAL_LOOKUP_CONSENT_DB
##########################

``type: str``

Which database (from DATABASES_) should be used to look up consent modes?


RESEARCH_DB_TITLE
#################

``type: str``

Research database title (displayed in web site).


.. _RESEARCH_DB_INFO:

RESEARCH_DB_INFO
################

``type: List[Dict[str, Any]]``

Defines the research database. This is the setting that allows CRATE to read
several arbitrary relational databases, and link them together helpfully for
features like the :ref:`SQL query builder <research_query_builder>`.

Note that *all* these databases use the ``DATABASES['research']`` connection
specified above.

This variable is a list of dictionaries, one per database. Each database
dictionary has the following keys, which are defined in
:class:`crate_anon.crateweb.config.constants.ResearchDbInfoKeys` (referred to
as ``RDIKeys`` in the settings file):

.. list-table::
    :widths: 25 10 65
    :header-rows: 1

    * - Key
      - Type
      - Value

    * - RDIKeys.NAME
      - ``str``
      - Unique name (for internal referencing)

    * - RDIKeys.DESCRIPTION
      - ``str``
      - Human-friendly description

    * - RDIKeys.DATABASE
      - ``str``
      - Database name, as seen by the database engine. For MySQL and
        PostgreSQL, use a blank string, ``''``. For SQL Server, use the
        database name.

    * - RDIKeys.SCHEMA
      - ``str``
      - Schema name. For MySQL, use the database (= schema) name. For
        PostgreSQL, use the schema name (usual default: ``'public''``). For SQL
        Server, use the schema name (usual default: ``'dbo'``).

    * - RDIKeys.PID_PSEUDO_FIELD
      - ``str``
      - String used as the name of a pseudo-field in some "clinician
        privileged" views, to representing the PID column. Offered in some
        views to look up patients based on PID, and elsewhere as the label for
        the PID column.

    * - RDIKeys.MPID_PSEUDO_FIELD
      - ``str``
      - String used as the name of a pseudo-field in some "clinician
        privileged" views, to representing the MPID column. Offered in some
        views to look up patients based on MPID, and elsewhere as the label for
        the MPID column.

    * - RDIKeys.TRID_FIELD
      - ``str``
      - Name of the TRID column within your anonymised research database.

    * - RDIKeys.RID_FIELD
      - ``str``
      - Name of the RID column within your anonymised research database.

    * - RDIKeys.RID_FAMILY
      - A "truthy" Python value (e.g. sequential integers).
      - **Explained below**; used to determine how CRATE cross-links multiple
        databases.

    * - RDIKeys.MRID_TABLE
      - ``str``
      - Name of a table within your anonymised research database that contains
        MRID values (and corresponding RIDs).

    * - RDIKeys.MRID_FIELD
      - ``str``
      - Name of the MRID column within the ``MRID_TABLE`` of your anonymised
        research database.

    * - RDIKeys.PID_DESCRIPTION
      - ``str``
      - Description of the PID field (e.g. "MyEPR number").

    * - RDIKeys.MPID_DESCRIPTION
      - ``str``
      - Description of the MPID field (e.g. "NHS number").

    * - RDIKeys.RID_DESCRIPTION
      - ``str``
      - Description of the RID field (e.g. "Research ID (RID; hashed MyEPR
        number)" or "BRCID").

    * - RDIKeys.MRID_DESCRIPTION
      - ``str``
      - Description of the MRID field (e.g. "Master research ID (MRID; hashed
        NHS number)").

    * - RDIKeys.TRID_DESCRIPTION
      - ``str``
      - Description of the TRID field (e.g. "Transient research ID (TRID) for
        database X").

    * - RDIKeys.SECRET_LOOKUP_DB
      - ``str``
      - To look up PID/RID mappings, provide a value that is a database alias
        from ``DATABASES``.

    * - RDIKeys.DEFAULT_DATE_FIELDS
      - ``List[str]``
      - For the data finder: is there a standard date field (column) for most
        patient tables? If so, specify one or more column names here. For
        example, ``["document_date", "record_date"]``.

    * - RDIKeys.DATE_FIELDS_BY_TABLE
      - ``Dict[str, str]``
      - For the data finder: if some tables have their own specific date
        columns, you can specify these here. If a table appears here, that
        overrides the values found in ``RDIKeys.DEFAULT_DATE_FIELDS``.
        Example: ``{"doc_table": "document_date", "diagnosis_table":
        "diagnosis_date"}``.

    * - RDIKeys.UPDATE_DATE_FIELD
      - ``str``
      - Name of a column indicating when the record was last updated in the
        database.

**More on databases and schemas**

- Under SQL Server, "database" and "schema" are different levels of
  organization. Specify a schema of ``"dbo"`` if you are unsure; this is the
  default.
- Under MySQL, "database" and "schema" mean the same thing. Here, we'll call
  this a SCHEMA.
- PostgreSQL can only query a single database via a single connection.
- The first database/schema in ``RESEARCH_DB_INFO`` is the default selected in
  CRATE's query builder.

**The RID_FAMILY parameter, and how CRATE auto-links tables**

CRATE's front end will automatically join tables, within and across multiple
research databases. In summary:

- WITHIN a schema, tables will be autojoined on the ``TRID_FIELD``.

- ACROSS schemas, tables will be autojoined on the ``RID_FIELD`` if they are in
  the same ``RID_FAMILY``, and on ``MRID_TABLE.MRID_FIELD`` otherwise.

In more detail:

The ``RID_FAMILY`` is part of the system that CRATE uses to cross-link multiple
research databases automatically (for the convenience of researchers using the
web front end).

A RID is present in all such research databases. However, different databases
may use different RIDs. If two databases use the same RID, they are part of the
same RID family (and CRATE will link them on RID). If they are not part of the
same RID family, CRATE will link them on MRID instead.

Here's an example:

=========== =============== =========== ==========
Database    PID/RID         MPID/MRID   RID family
=========== =============== =========== ==========
DbOne       RiO number      NHS number  1
DbTwo       RiO number      NHS number  1
DbThree     Epic number     NHS number  2
DbFour      SystmOne number NHS number  3
=========== =============== =========== ==========

(In all cases, the RID is assumed to be a hashed version of the PID.)

Here, DbOne and DbTwo share a RID, so are part of the same RID family (and can
be linked directly on RID if a query asks for data from both). The others use
different RIDs, so are part of separate RID families -- cross-linkage requires
CRATE to use the MRID as an intermediate in the linking step.

**Date/time columns for the data finder**

The application of ``RDIKeys.DATE_FIELDS_BY_TABLE`` and
``RDIKeys.DEFAULT_DATE_FIELDS`` is performed
by :meth:`crate_anon.crateweb.research.research_db_info.SingleResearchDatabase.get_default_date_field`.


RESEARCH_DB_FOR_CONTACT_LOOKUP
##############################

``type: str``

Which database (from those defined in RESEARCH_DB_INFO_ above) should be used
to look up patients when contact requests are made?

Give the ``name`` attribute of one of the databases in RESEARCH_DB_INFO_.
Its ``secret_lookup_db`` will be used for the actual lookup process.


NLP_SOURCEDB_MAP
################

``type: Dict[str, str]``

This is an optional setting.

Used to provide automatic links from results involving CRATE NLP tables. Such
tables have :ref:`standard NLP output columns <standard_nlp_output_columns>`.
When the CRATE web front end detects a table, it tries to provide a hyperlink
to the original data, if available. However, database names in these tables
(the ``_srcdb`` column) are user-defined.

In ``NLP_SOURCEDB_MAP``, you can provide a mapping from ``_srcdb`` names to the
names of databases in RESEARCH_DB_INFO_, and this will enable the auto-linking.


RESEARCH_DB_DIALECT
###################

``type: str``

For the automatic query generator, we need to know the underlying SQL dialect.
Options are

- ``mysql`` = MySQL
- ``mssql`` = Microsoft SQL Server


DISABLE_DJANGO_PYODBC_AZURE_CURSOR_FETCHONE_NEXTSET
###################################################

``type: bool``

*Default: True.*

If True, calls
:func:`crate_anon.crateweb.research.models.hack_django_pyodbc_azure_cursorwrapper`
at startup (q.v.).


.. _webconfig_archive:

Archive views
-------------

.. _ARCHIVE_TEMPLATE_DIR:

ARCHIVE_TEMPLATE_DIR
####################

``type: str``

*Optional.*

Root directory of the :ref:`archive <archive>` template system.


ARCHIVE_ROOT_TEMPLATE
#####################

``type: str``

*Optional.*

Filename of the :ref:`archive <archive>`'s root template. This should be
found within ARCHIVE_TEMPLATE_DIR_.


ARCHIVE_ATTACHMENT_DIR
######################

``type: str``

*Optional.*

Root directory for archive attachments.


.. _ARCHIVE_STATIC_DIR:

ARCHIVE_STATIC_DIR
##################

``type: str``

*Optional.*

Root directory for archive static files.


.. _ARCHIVE_TEMPLATE_CACHE_DIR:

ARCHIVE_TEMPLATE_CACHE_DIR
##########################

``type: str``

*Optional.*

Directory in which to store compiled versions of the archive templates.


.. _ARCHIVE_CONTEXT:

ARCHIVE_CONTEXT
###############

``type: Dict[str, Any]``

*Optional.*

A dictionary that forms the basis of the Python context within archive
templates. See :ref:`archive Python context <archive_mako_context>`.


.. _CACHE_CONTROL_MAX_AGE_ARCHIVE_STATIC:

CACHE_CONTROL_MAX_AGE_ARCHIVE_STATIC
####################################

``type: int``

*Optional; default 0.*

Ask client browsers to cache files from the static part of the archive up to
this maximum age in seconds. (This sets the ``Cache-Control:
max-age=<seconds>`` parameter in the HTTP header.)

CRATE will add file modification times to URLs, so setting a long cache expiry
time will not prevent automatic reloading if the file changes.


CACHE_CONTROL_MAX_AGE_ARCHIVE_ATTACHMENTS
#########################################

``type: int``

*Optional; default 0.*

As for CACHE_CONTROL_MAX_AGE_ARCHIVE_STATIC_, but for attachments within the
archive.


CACHE_CONTROL_MAX_AGE_ARCHIVE_TEMPLATES
#######################################

``type: int``

*Optional; default 0.*

As for CACHE_CONTROL_MAX_AGE_ARCHIVE_STATIC_, but for calls to render
templates.


Site-specific help
------------------

.. _DATABASE_HELP_HTML_FILENAME:

DATABASE_HELP_HTML_FILENAME
###########################

``type: Optional[str]``

If specified, this must be a string that is an absolute filename of **trusted**
HTML that will be provided to the user when they ask for site-specific help on
your database structure (see :ref:`Help on local database structure
<help_local_database_structure>`).


Local file storage
------------------

PRIVATE_FILE_STORAGE_ROOT
#########################

``type: str``

Where should we store binary files uploaded to CRATE (e.g. study leaflets)?
Specify a directory name here. You should create this directory (and don't let
it be served by a generic web server that doesn't check permissions).


XSENDFILE
#########

``type: bool``

Specify ``False`` to serve files via Django (inefficient but useful for
testing) or ``True`` to serve via Apache with ``mod_xsendfile`` (or another web
server configured for the X-SendFile directive).

This setting is read by :func:`cardinal_pythonlib.django.serve.serve_file`,
called by several functions within :mod:`crate_anon.crateweb.consent.views`.


MAX_UPLOAD_SIZE_BYTES
#####################

``type: int``

How big an upload will we accept? Example:

.. code-block:: python

    MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 Mb


Outgoing e-mail
---------------

EMAIL_*
#######

First, there are general settings for sending e-mail from Django; see
https://docs.djangoproject.com/en/1.8/ref/settings/#email-backend. Example:

.. code-block:: python

    #   default backend:
    # EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    #   bugfix for servers that only support TLSv1:
    # EMAIL_BACKEND = 'cardinal_pythonlib.django.mail.SmtpEmailBackendTls1'

    EMAIL_HOST = 'smtp.somewhere.nhs.uk'
    EMAIL_PORT = 587  # usually 25 (plain SMTP) or 587 (STARTTLS)
    # ... see https://www.fastmail.com/help/technical/ssltlsstarttls.html
    EMAIL_HOST_USER = 'myuser'
    EMAIL_HOST_PASSWORD = 'mypassword'
    EMAIL_USE_TLS = True
    EMAIL_USE_SSL = False

    # Who will the e-mails appear to come from?
    EMAIL_SENDER = "My NHS Trust Research Database - DO NOT REPLY <noreply@somewhere.nhs.uk>"  # noqa

Then there are some additional custom settings:


.. _SAFETY_CATCH_ON:

SAFETY_CATCH_ON
###############

``type: bool``

During development, we set this to ``True`` to route all consent-related
e-mails to the developer, specified by DEVELOPER_EMAIL_. Switch
``SAFETY_CATCH_ON`` to ``False`` for production mode.


.. _DEVELOPER_EMAIL:

DEVELOPER_EMAIL
###############

``type: str``

E-mail address of a person developing CRATE (for SAFETY_CATCH_ON_).


VALID_RESEARCHER_EMAIL_DOMAINS
##############################

``type: List[str]``

List of e-mail domains, such as ``["@cpft.nhs.uk"]``, which are acceptable to
you for researchers. If this list is empty, CRATE will send e-mails to
researchers (via the e-mail configured in their user settings) without further
checks. If it's not empty, though, CRATE will refuse to send researcher e-mails
-- which will often contain patient-identifiable information, as part of the
consent-to-contact system -- unless the researcher's e-mail domain is in this
list. Setting this prevents e-mails going to an inappropriate domain even if
the researcher sets their e-mail to something insecure, e.g.
``someone@hotmail.com``.



Research Database Manager (RDBM) settings
-----------------------------------------

RDBM_NAME
#########

``type: str``

Name of the RDBM, e.g. "John Smith".


RDBM_TITLE
##########

``type: str``

The RDBM's title, e.g. "Research Database Manager".


RDBM_TELEPHONE
##############

``type: str``

The RDBM's telephone number, which is provided to clinicians and researchers.


.. _RDBM_EMAIL:

RDBM_EMAIL
##########

``type: str``

E-mail address of the Research Database Manager (RDBM).


RDBM_ADDRESS
############

``type: List[str]``

The address of the RDBM (as a list of address lines). This address is used in
communication to patients. Example: ``["FREEPOST SOMEWHERE_HOSPITAL RESEARCH
DATABASE MANAGER"]``.


Web site administrators
-----------------------

ADMINS
######

``type: List[Tuple[str, str], ...]``

This is a list of ``(name, email_address)`` pairs. Software exception reports
get sent to these people.

This is a Django setting; see
https://docs.djangoproject.com/en/2.2/ref/settings/#std:setting-ADMINS.


PDF creation
------------

WKHTMLTOPDF_FILENAME
####################

``type: str``

Absolute path to the wkhtmltopdf_ executable.

You must specify one that incorporates any need for an X Server (not the default
``/usr/bin/wkhtmltopdf``). See http://stackoverflow.com/questions/9604625/. In
brief, you can try

.. code-block:: python

    WKHTMLTOPDF_FILENAME = ''

to use the default, and if that fails, try

.. code-block:: python

    WKHTMLTOPDF_FILENAME = '/usr/bin/wkhtmltopdf'

and that should work if your version of wkhtmltopdf is a "headless" one using
"patched Qt"; but if that fails, use

.. code-block:: python

    WKHTMLTOPDF_FILENAME = '/path/to/wkhtmltopdf.sh'

where ``wkhtmltopdf.sh`` is an executable script (``chmod a+x ...``)
containing:

.. code-block:: bash

    #!/usr/bin/env bash
    xvfb-run --auto-servernum --server-args="-screen 0 640x480x16" \
        /usr/bin/wkhtmltopdf "$@"

For a recent version of ``wkhtmltopdf``, fetch one from
http://wkhtmltopdf.org/, e.g. v0.12.4 for your OS. Make sure you use one for
"patched Qt".


WKHTMLTOPDF_OPTIONS
###################

``type: Dict[str, str]``

Additional dictionary passed via pdfkit_ to wkhtmltopdf_. See
https://wkhtmltopdf.org/usage/wkhtmltopdf.txt. Specimen:

.. code-block:: python

    WKHTMLTOPDF_OPTIONS = {  # dict for pdfkit
        "page-size": "A4",
        "margin-left": "20mm",
        "margin-right": "20mm",
        "margin-top": "21mm",  # from paper edge down to top of content?
        "margin-bottom": "24mm",  # from paper edge up to bottom of content?
        "header-spacing": "3",  # mm, from content up to bottom of header
        "footer-spacing": "3",  # mm, from content down to top of footer
    }


.. _PDF_LOGO_ABS_URL:

PDF_LOGO_ABS_URL
################

``type: str``

Absolute URL to a file on your server containing a logo to be incorporated into
PDFs generated by CRATE -- typically, your institutional logo.

This URL is read by ``wkhtmltopdf``. Example:

.. code-block:: python

    PDF_LOGO_ABS_URL = 'http://localhost/crate_logo'
    # ... path on local machine, read by wkhtmltopdf
    # Examples:
    #   [if you're running a web server] 'http://localhost/crate_logo'
    #   [Linux root path] file:///home/myuser/myfile.png
    #   [Windows root path] file:///c:/path/to/myfile.png


PDF_LOGO_WIDTH
##############

``type: str``

Logo width, passed to an ``<img>`` tag in the HTML used to build PDF files.
Tune this to your logo file (see PDF_LOGO_ABS_URL_). Example:

.. code-block:: python

    PDF_LOGO_WIDTH = "75%"
    # ... must be suitable for an <img> tag, but "150mm" isn't working; "75%" is.


TRAFFIC_LIGHT_*
###############

The PDF generator also needs to be able to find the traffic-light icons, on
disk (not via your web site), so specify ``file://`` URLs for the following:

.. code-block:: python

    TRAFFIC_LIGHT_RED_ABS_URL = 'file:///somewhere/crate_anon/crateweb/static/red.png'  # noqa
    TRAFFIC_LIGHT_YELLOW_ABS_URL = 'file:///somewhere/crate_anon/crateweb/static/yellow.png'  # noqa
    TRAFFIC_LIGHT_GREEN_ABS_URL = 'file:///somewhere/crate_anon/crateweb/static/green.png'  # noqa


Consent-for-contact settings
----------------------------

PERMITTED_TO_CONTACT_DISCHARGED_PATIENTS_FOR_N_DAYS
###################################################

``type: int``

For how long (in days) after discharge may we contact discharged patients
without specific permission? Use 0 for "not at all".


CHARITY_AMOUNT_CLINICIAN_RESPONSE
#################################

``type: float``

Amount to be donated by your organization to charity for each clinician
response (regardless of the clinician's decision). Units are your local
currency (e.g. GBP).


.. _PDF_LETTER_HEADER_HTML:

PDF_LETTER_HEADER_HTML
######################

``type: str``

HTML (which may be an empty string) to use as the header for wkhtmltopdf_.

Note that using headers/footers requires a version of wkhtmltopdf built using
"patched Qt"; see above.

Examples:

.. code-block:: python

    PDF_LETTER_HEADER_HTML = ''

.. code-block:: python

    PDF_LETTER_HEADER_HTML = '''
    <!DOCTYPE html>
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    </head>
    <html>
        <body>
            <div>boo! header</div>
        </body>
    </html>
    '''


PDF_LETTER_FOOTER_HTML
######################

``type: str``

See PDF_LETTER_HEADER_HTML_.

Examples:

.. code-block:: python

    PDF_LETTER_FOOTER_HTML = ''

.. code-block:: python

    # http://stackoverflow.com/questions/11948158/wkhtmltopdf-how-to-disable-header-on-the-first-page  # noqa
    PDF_LETTER_FOOTER_HTML = '''
    <!DOCTYPE html>
    <html>
        <head>
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
            <script>
    function restrict_page_display() {
        var vars = {},
            kvp_list = document.location.search.substring(1).split('&'),
            key_value_pair,
            debug_element = document.getElementById("debug"),
            i;
        for (i = 0; i < kvp_list.length; ++i) {
            key_value_pair = kvp_list[i].split('=', 2);
            vars[key_value_pair[0]] = unescape(key_value_pair[1]);
        }
        // debug_element.textContent = kvp_list;

        // Turn off footer except on first page
        if (vars['page'] != 1) {
            document.getElementById("footer").style.display = 'none';
        }
    }
            </script>
            <style>
    body {
        color: #005EB8;  /* NHS Blue */
        font-family: Arial, Helvetica, sans-serif;
        font-size: small;
        text-align: right;
    }
            </style>
        </head>
        <!-- <body onload="restrict_page_display()"> -->
        <body>
            <div id="footer">
                CPFT
                | HQ: Elizabeth House, Fulbourn Hospital, Fulbourn,
                  Cambridge CB21 5EF
                | www.cpft.nhs.uk
            </div>
            <div id="debug"></div>
        </body>
    </html>
    '''


Local information links
-----------------------

.. _CHARITY_URL:

CHARITY_URL
###########

``type: str``

Absolute URL to an information page about your charity donation system, e.g.

.. code-block:: python

    CHARITY_URL = "http://www.cpft.nhs.uk/research.htm"


CHARITY_URL_SHORT
#################

Short "humanized" version of CHARITY_URL_, for use as clickable text; e.g.

.. code-block:: python

    CHARITY_URL_SHORT = "www.cpft.nhs.uk/research.htm"


LEAFLET_URL_CPFTRD_CLINRES_SHORT
################################

Short "humanized" version of CHARITY_URL_, for use in printed PDFs such as
leaflets; e.g.

.. code-block:: python

    LEAFLET_URL_CPFTRD_CLINRES_SHORT = "www.cpft.nhs.uk/research.htm > CPFT Research Database"  # noqa

PUBLIC_RESEARCH_URL_SHORT
#########################

Another version of CHARITY_URL_; e.g.

.. code-block:: python

    PUBLIC_RESEARCH_URL_SHORT = "www.cpft.nhs.uk/research.htm"

.. todo:: is this one currently unused? Looks like it.


Specimen config file
--------------------

To obtain a specimen file, use

.. _crate_print_demo_crateweb_config:

.. code-block:: none

    crate_print_demo_crateweb_config

Specimen web config:

..  literalinclude:: specimen_web_config.py
    :language: python
