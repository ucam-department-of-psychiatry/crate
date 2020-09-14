# (Don't use a shebang; Lintian will complain "script-not-executable".)

"""
crate_anon/crateweb/specimen_secret_local_settings/crateweb_local_settings.py

===============================================================================

    Copyright (C) 2015-2020 Rudolf Cardinal (rudolf@pobox.com).

    This file is part of CRATE.

    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.

===============================================================================

**Site-specific Django settings for CRATE web front end.**

Put the secret stuff here.

SPECIMEN FILE ONLY - edit to your own requirements.
IT WILL NOT WORK until you've edited it.

For help, see
https://crateanon.readthedocs.io/en/latest/website_config/web_config_file.html

"""

import logging
import os
from typing import List, TYPE_CHECKING

# Include the following if you want to use it in CELERYBEAT_SCHEDULE
# from celery.schedules import crontab

from crate_anon.crateweb.config.constants import ResearchDbInfoKeys as RDIKeys

if TYPE_CHECKING:
    from django.http.request import HttpRequest

log = logging.getLogger(__name__)

log.critical(
    "Well done - CRATE has found your crate_local_settings.py file at {}. "
    "However, you need to configure it for your institution's set-up, and "
    "remove this line.".format(os.path.abspath(__file__)))


# =============================================================================
# Site URL configuration
# =============================================================================
# See https://crateanon.readthedocs.io/en/latest/website_config/web_config_file.html  # noqa

DJANGO_SITE_ROOT_ABSOLUTE_URL = "http://mymachine.mydomain"  # example for Apache  # noqa
# DJANGO_SITE_ROOT_ABSOLUTE_URL = "http://localhost:8000"  # for the Django dev server  # noqa

FORCE_SCRIPT_NAME = ""
# FORCE_SCRIPT_NAME = "/crate"  # example for CherryPy or Apache non-root hosting  # noqa


# =============================================================================
# Site security
# =============================================================================
# See https://crateanon.readthedocs.io/en/latest/website_config/web_config_file.html  # noqa

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'  # CHANGE THIS!  # noqa
# Run crate_generate_new_django_secret_key to generate a new one.

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False
# ... when False, note that static files must be served properly

CRATE_HTTPS = True  # require HTTPS and disallow plain HTTP


# noinspection PyUnusedLocal
def always_show_toolbar(request: "HttpRequest") -> bool:
    return True  # Always show toolbar, for debugging only.


if DEBUG:
    ALLOWED_HOSTS = []  # type: List[str]
    DEBUG_TOOLBAR_CONFIG = {
        'SHOW_TOOLBAR_CALLBACK': always_show_toolbar,
    }
else:
    ALLOWED_HOSTS = ['*']


# =============================================================================
# Celery configuration
# =============================================================================
# See https://crateanon.readthedocs.io/en/latest/website_config/web_config_file.html  # noqa


# =============================================================================
# Database configuration
# =============================================================================
# See https://crateanon.readthedocs.io/en/latest/website_config/web_config_file.html  # noqa

DATABASES = {
    # See https://docs.djangoproject.com/en/1.8/ref/settings/#databases

    # -------------------------------------------------------------------------
    # Django database for web site (inc. users, audit).
    # -------------------------------------------------------------------------

    # Quick SQLite example:
    # 'default': {
    #     'ENGINE': 'django.db.backends.sqlite3',
    #     'NAME': '/home/myuser/somewhere/crate_db.sqlite3',
    # },

    # Quick MySQL example:
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'HOST': '127.0.0.1',
        'PORT': 3306,  # local
        'NAME': 'crate_db',
        'USER': 'someuser',
        'PASSWORD': 'somepassword',
    },

    # -------------------------------------------------------------------------
    # Anonymised research database
    # -------------------------------------------------------------------------
    'research': {

        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        # IT IS CRITICALLY IMPORTANT THAT THIS CONNECTION (i.e. its user's
        # access) IS READ-ONLY FOR THE RESEARCH DATABASES [1] AND HAS NO
        # ACCESS WHATSOEVER TO SECRET DATABASES (like the 'default' or
        # 'secret' databases) [2]. RESEARCHERS ARE GIVEN FULL ABILITY TO
        # EXECUTE SQL VIA THIS CONNECTION, AND CAN DO SO FOR ANY DATABASES
        # THAT THE CONNECTION PERMITS, NOT JUST THE ONE YOU SPECIFY
        # EXPLICITLY.
        #
        # [1] ... so researchers can't alter/delete research data
        # [2] ... so researchers can't see secrets
        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

        'ENGINE': 'django.db.backends.mysql',
        'HOST': '127.0.0.1',
        'PORT': 3306,  # local
        'NAME': 'anonymous_output',  # will be the default database; use None for no default database  # noqa
        'USER': 'researcher',
        'PASSWORD': 'somepassword',
    },

    # -------------------------------------------------------------------------
    # One or more secret databases for RID/PID mapping
    # -------------------------------------------------------------------------
    'secret_1': {
        'ENGINE': 'django.db.backends.mysql',
        'HOST': '127.0.0.1',
        'PORT': 3306,
        'NAME': 'anonymous_mapping',
        'USER': 'anonymiser_system',
        'PASSWORD': 'somepassword',
    },

    # -------------------------------------------------------------------------
    # Others, for consent lookup
    # -------------------------------------------------------------------------

    # Optional: 'cpft_crs'
    # Optional: 'cpft_pcmis'
    # Optional: 'cpft_rio_crate'
    # Optional: 'cpft_rio_datamart'
    # Optional: 'cpft_rio_raw'
    # Optional: 'cpft_rio_rcep'
    # ... see ClinicalDatabaseType in crate_anon/crateweb/config/constants.py
}

# Which database should be used to look up demographic details?
CLINICAL_LOOKUP_DB = 'dummy_clinical'

# Which database should be used to look up consent modes?
CLINICAL_LOOKUP_CONSENT_DB = 'dummy_clinical'

# Research database title (displayed in web site)
RESEARCH_DB_TITLE = "My NHS Trust Research Database"

# Database structure information for CRATE's query builders.
# See https://crateanon.readthedocs.io/en/latest/website_config/web_config_file.html  # noqa
RESEARCH_DB_INFO = [
    {
        # Unique name:
        RDIKeys.NAME: 'myresearchdb',

        # Human-friendly description:
        RDIKeys.DESCRIPTION: 'My friendly research database',

        # Database name as seen by the database engine:
        # - BLANK, i.e. '', for MySQL.
        # - BLANK, i.e. '', for PostgreSQL.
        # - The database name, for SQL Server.
        RDIKeys.DATABASE: '',

        # Schema name:
        # - The database=schema name, for MySQL.
        # - The schema name, for PostgreSQL (usual default: 'public').
        # - The schema name, for SQL Server (usual default: 'dbo').
        RDIKeys.SCHEMA: 'dbo',

        # Fields not in the database, but used for SELECT AS statements for
        # some clinician views:
        RDIKeys.PID_PSEUDO_FIELD: 'my_pid_field',
        RDIKeys.MPID_PSEUDO_FIELD: 'my_mpid_field',

        # Fields and tables found within the database:
        RDIKeys.TRID_FIELD: 'trid',
        RDIKeys.RID_FIELD: 'brcid',
        RDIKeys.RID_FAMILY: 1,
        RDIKeys.MRID_TABLE: 'patients',
        RDIKeys.MRID_FIELD: 'nhshash',

        # Descriptions, used for PID lookup and the like
        RDIKeys.PID_DESCRIPTION: 'Patient ID (My ID Num; PID) for database X',
        RDIKeys.MPID_DESCRIPTION: 'Master patient ID (NHS number; MPID)',
        RDIKeys.RID_DESCRIPTION: 'Research ID (RID) for database X',
        RDIKeys.MRID_DESCRIPTION: 'Master research ID (MRID)',
        RDIKeys.TRID_DESCRIPTION: 'Transient research ID (TRID) for database X',

        # To look up PID/RID mappings, provide a key for 'secret_lookup_db'
        # that is a database alias from DATABASES:
        RDIKeys.SECRET_LOOKUP_DB: 'secret_1',

        # For the data finder: table-specific and default date column names
        RDIKeys.DATE_FIELDS_BY_TABLE: {},
        RDIKeys.DEFAULT_DATE_FIELDS: ['default_date_field'],

        # Column name giving time that record was updated
        RDIKeys.UPDATE_DATE_FIELD: '_when_fetched_utc',
    },
    {
        RDIKeys.NAME: 'similar_database',
        RDIKeys.DESCRIPTION: 'A database sharing the RID with the first',

        RDIKeys.DATABASE: 'similar_database',
        RDIKeys.SCHEMA: 'similar_schema',
        RDIKeys.TRID_FIELD: 'trid',
        RDIKeys.RID_FIELD: 'same_rid',
        RDIKeys.RID_FAMILY: 1,
        RDIKeys.MRID_TABLE: '',
        RDIKeys.MRID_FIELD: '',

        RDIKeys.PID_DESCRIPTION: '',
        RDIKeys.MPID_DESCRIPTION: '',
        RDIKeys.RID_DESCRIPTION: '',
        RDIKeys.MRID_DESCRIPTION: '',
        RDIKeys.TRID_DESCRIPTION: '',

        RDIKeys.SECRET_LOOKUP_DB: '',

        RDIKeys.DATE_FIELDS_BY_TABLE: {},
        RDIKeys.DEFAULT_DATE_FIELDS: [],

        RDIKeys.UPDATE_DATE_FIELD: '_when_fetched_utc',
    },
    {
        RDIKeys.NAME: 'different_database',
        RDIKeys.DESCRIPTION: 'A database sharing only the MRID with the first',

        RDIKeys.DATABASE: 'different_database',
        RDIKeys.SCHEMA: 'different_schema',
        RDIKeys.TRID_FIELD: 'trid',
        RDIKeys.RID_FIELD: 'different_rid',
        RDIKeys.RID_FAMILY: 2,
        RDIKeys.MRID_TABLE: 'hashed_nhs_numbers',
        RDIKeys.MRID_FIELD: 'nhshash',

        RDIKeys.PID_DESCRIPTION: '',
        RDIKeys.MPID_DESCRIPTION: '',
        RDIKeys.RID_DESCRIPTION: '',
        RDIKeys.MRID_DESCRIPTION: '',
        RDIKeys.TRID_DESCRIPTION: '',

        RDIKeys.SECRET_LOOKUP_DB: '',

        RDIKeys.DATE_FIELDS_BY_TABLE: {},
        RDIKeys.DEFAULT_DATE_FIELDS: [],

        RDIKeys.UPDATE_DATE_FIELD: '_when_fetched_utc',
    },
]

# Which database (from those defined in RESEARCH_DB_INFO above) should be used
# to look up patients when contact requests are made?
# Give the 'name' attribute of one of the databases in RESEARCH_DB_INFO.
# Its secret_lookup_db will be used for the actual lookup process.
RESEARCH_DB_FOR_CONTACT_LOOKUP = 'myresearchdb'

# Definitions of source database names in CRATE NLP tables
NLP_SOURCEDB_MAP = {'SOURCE_DATABASE': 'research'}

# For the automatic query generator, we need to know the underlying SQL dialect
# Options are
# - 'mysql' => MySQL
# - 'mssql' => Microsoft SQL Server
RESEARCH_DB_DIALECT = 'mysql'

DISABLE_DJANGO_PYODBC_AZURE_CURSOR_FETCHONE_NEXTSET = True

# =============================================================================
# Archive views
# =============================================================================
# See https://crateanon.readthedocs.io/en/latest/website_config/web_config_file.html  # noqa

ARCHIVE_TEMPLATE_DIR = "/home/somewhere/my_archive_templates"
ARCHIVE_STATIC_DIR = "/home/somewhere/my_archive_templates/static"
ARCHIVE_ROOT_TEMPLATE = "root.mako"
ARCHIVE_ATTACHMENT_DIR = "/home/somewhere/my_archive_attachments"
ARCHIVE_CONTEXT = {}
CACHE_CONTROL_MAX_AGE_ARCHIVE_ATTACHMENTS = 0
CACHE_CONTROL_MAX_AGE_ARCHIVE_TEMPLATES = 0
CACHE_CONTROL_MAX_AGE_ARCHIVE_STATIC = 0


# =============================================================================
# Database extra help file
# =============================================================================
# See https://crateanon.readthedocs.io/en/latest/website_config/web_config_file.html  # noqa

# If specified, this must be a string that is an absolute filename of TRUSTED
# HTML that will be included.
DATABASE_HELP_HTML_FILENAME = None


# =============================================================================
# Local file storage (for PDFs etc).
# =============================================================================
# See https://crateanon.readthedocs.io/en/latest/website_config/web_config_file.html  # noqa

# Where should we store the files? Make this directory (and don't let it
# be served by a generic web server that doesn't check permissions).
PRIVATE_FILE_STORAGE_ROOT = '/srv/crate_filestorage'

# Serve files via Django (inefficient but useful for testing) or via Apache
# with mod_xsendfile (or other web server configured for the X-SendFile
# directive)?
XSENDFILE = False

# How big will we accept?
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 Mb


# =============================================================================
# Outgoing e-mail
# =============================================================================
# See https://crateanon.readthedocs.io/en/latest/website_config/web_config_file.html  # noqa

# -----------------------------------------------------------------------------
# General settings for sending e-mail from Django
# -----------------------------------------------------------------------------
# https://docs.djangoproject.com/en/1.8/ref/settings/#email-backend

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

# -----------------------------------------------------------------------------
# Additional settings
# -----------------------------------------------------------------------------
# See https://crateanon.readthedocs.io/en/latest/website_config/web_config_file.html  # noqa

# During development, we route all consent-related e-mails to the developer.
# Switch SAFETY_CATCH_ON to False for production mode.
SAFETY_CATCH_ON = True
DEVELOPER_EMAIL = "testuser@somewhere.nhs.uk"

VALID_RESEARCHER_EMAIL_DOMAINS = []  # type: List[str]
# ... if empty, no checks are performed (any address is accepted)


# =============================================================================
# Research Database Manager (RDBM) details
# =============================================================================
# See https://crateanon.readthedocs.io/en/latest/website_config/web_config_file.html  # noqa

RDBM_NAME = "John Doe"
RDBM_TITLE = "Research Database Manager"
RDBM_TELEPHONE = "01223-XXXXXX"
RDBM_EMAIL = "research.database@somewhere.nhs.uk"
RDBM_ADDRESS = ["FREEPOST SOMEWHERE_HOSPITAL RESEARCH DATABASE MANAGER"]  # a list  # noqa


# =============================================================================
# Administrators/managers to be notified of errors
# =============================================================================
# See https://crateanon.readthedocs.io/en/latest/website_config/web_config_file.html  # noqa

# Exceptions get sent to these people.
ADMINS = [
    ('Mr Administrator', 'mr_admin@somewhere.domain'),
]


# =============================================================================
# PDF creation
# =============================================================================
# See https://crateanon.readthedocs.io/en/latest/website_config/web_config_file.html  # noqa

WKHTMLTOPDF_FILENAME = ''
# WKHTMLTOPDF_FILENAME = '/home/rudolf/dev/wkhtmltopdf/wkhtmltox/bin/wkhtmltopdf'  # noqa
# WKHTMLTOPDF_FILENAME = '/usr/bin/wkhtmltopdf'

WKHTMLTOPDF_OPTIONS = {  # dict for pdfkit
    "page-size": "A4",
    "margin-left": "20mm",
    "margin-right": "20mm",
    "margin-top": "21mm",  # from paper edge down to top of content?
    "margin-bottom": "24mm",  # from paper edge up to bottom of content?
    "header-spacing": "3",  # mm, from content up to bottom of header
    "footer-spacing": "3",  # mm, from content down to top of footer
}

PDF_LOGO_ABS_URL = 'http://localhost/crate_logo'
# ... path on local machine, read by wkhtmltopdf
# Examples:
#   [if you're running a web server] 'http://localhost/crate_logo'
#   [Linux root path] file:///home/myuser/myfile.png
#   [Windows root path] file:///c:/path/to/myfile.png

PDF_LOGO_WIDTH = "75%"
# ... must be suitable for an <img> tag, but "150mm" isn't working; "75%" is.
# ... tune this to your logo file (see PDF_LOGO_ABS_URL)

# The PDF generator also needs to be able to find the traffic-light pictures,
# on disk (not via your web site):
TRAFFIC_LIGHT_RED_ABS_URL = 'file:///somewhere/crate_anon/crateweb/static/red.png'  # noqa
TRAFFIC_LIGHT_YELLOW_ABS_URL = 'file:///somewhere/crate_anon/crateweb/static/yellow.png'  # noqa
TRAFFIC_LIGHT_GREEN_ABS_URL = 'file:///somewhere/crate_anon/crateweb/static/green.png'  # noqa


# =============================================================================
# Consent-for-contact settings
# =============================================================================
# See https://crateanon.readthedocs.io/en/latest/website_config/web_config_file.html  # noqa

# For how long may we contact discharged patients without specific permission?
# Use 0 for "not at all".
PERMITTED_TO_CONTACT_DISCHARGED_PATIENTS_FOR_N_DAYS = 3 * 365

# Donation to charity for clinician response (regardless of the decision):
CHARITY_AMOUNT_CLINICIAN_RESPONSE = 1.0  # in local currency, e.g. GBP

# Note that using headers/footers requires a version of wkhtmltopdf built using
# "patched Qt". See above.
# Fetch one from http://wkhtmltopdf.org/, e.g. v0.12.4 for your OS.
PDF_LETTER_HEADER_HTML = ''
PDF_LETTER_FOOTER_HTML = ''


# =============================================================================
# Local information links
# =============================================================================
# See https://crateanon.readthedocs.io/en/latest/website_config/web_config_file.html  # noqa

CHARITY_URL = "http://www.cpft.nhs.uk/research.htm"
CHARITY_URL_SHORT = "www.cpft.nhs.uk/research.htm"
LEAFLET_URL_CPFTRD_CLINRES_SHORT = "www.cpft.nhs.uk/research.htm > CPFT Research Database"  # noqa
