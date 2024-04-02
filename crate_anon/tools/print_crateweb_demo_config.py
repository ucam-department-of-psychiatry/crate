#!/usr/bin/env python

"""
crate_anon/tools/print_crateweb_demo_config.py

===============================================================================

    Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

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
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

===============================================================================

**Print a demonstration CRATE web (Django) config file.**

"""
import argparse
import pprint
import re
import sys
from typing import Dict

from rich_argparse import RichHelpFormatter

from crate_anon.common.constants import EXIT_FAILURE

DEMO_CONFIG = r"""
# **Site-specific Django settings for CRATE web front end.**

# Put the secret stuff here.

# SPECIMEN FILE ONLY - edit to your own requirements.
# IT WILL NOT WORK until you've edited it.

# For help, see
# https://crateanon.readthedocs.io/en/latest/website_config/web_config_file.html

import logging
import os
import shutil
from typing import List, TYPE_CHECKING

# Include the following if you want to use it in CELERYBEAT_SCHEDULE
# from celery.schedules import crontab

from crate_anon.common.constants import mebibytes
from crate_anon.crateweb.config.constants import ResearchDbInfoKeys as RDIKeys
from crate_anon.crateweb.consent.constants import CPFTEthics2022

if TYPE_CHECKING:
    from django.http.request import HttpRequest

log = logging.getLogger(__name__)

log.critical(
    "Well done - CRATE has found your crate_local_settings.py file at {}. "
    "However, you need to configure it for your institution's set-up, and "
    "remove this line.".format(os.path.abspath(__file__))
)


# =============================================================================
# Site URL configuration
# =============================================================================
# See https://crateanon.readthedocs.io/en/latest/website_config/web_config_file.html  # noqa

# DJANGO_SITE_ROOT_ABSOLUTE_URL = "http://mymachine.mydomain"  # example for Apache  # noqa
# DJANGO_SITE_ROOT_ABSOLUTE_URL = "http://localhost:8000"  # for the Django dev server  # noqa
DJANGO_SITE_ROOT_ABSOLUTE_URL = "@@django_site_root_absolute_url@@"

FORCE_SCRIPT_NAME = "@@force_script_name@@"
# FORCE_SCRIPT_NAME = ""  # example for Apache root hosting
# FORCE_SCRIPT_NAME = "/crate"  # example for CherryPy or Apache non-root hosting  # noqa


# =============================================================================
# Site security
# =============================================================================
# See https://crateanon.readthedocs.io/en/latest/website_config/web_config_file.html  # noqa

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "@@secret_key@@"
# Run crate_generate_new_django_secret_key to generate a new one.

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False
# ... when False, note that static files must be served properly

CRATE_HTTPS = @@crate_https@@  # True: require HTTPS and disallow plain HTTP


# noinspection PyUnusedLocal
def always_show_toolbar(request: "HttpRequest") -> bool:
    return True  # Always show toolbar, for debugging only.


if DEBUG:
    ALLOWED_HOSTS = []  # type: List[str]
    DEBUG_TOOLBAR_CONFIG = {
        "SHOW_TOOLBAR_CALLBACK": always_show_toolbar,
    }
else:
    ALLOWED_HOSTS = ["*"]


# =============================================================================
# Celery configuration
# =============================================================================
# See https://crateanon.readthedocs.io/en/latest/website_config/web_config_file.html  # noqa

BROKER_URL = "@@broker_url@@"

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
    "default": {
        "ENGINE": "@@crate_db_engine@@",
        "HOST": "@@crate_db_host@@",  # e.g. 127.0.0.1
        "PORT": "@@crate_db_port@@",  # local e.g. 3306
        "NAME": "@@crate_db_name@@",
        "USER": "@@crate_db_user@@",
        "PASSWORD": "@@crate_db_password@@",
    },
    # -------------------------------------------------------------------------
    # Anonymised research database
    # -------------------------------------------------------------------------
    "research": {
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
        "ENGINE": "@@dest_db_engine@@",
        "HOST": "@@dest_db_host@@",  # e.g. 127.0.0.1
        "PORT": "@@dest_db_port@@",  # local, e.g. 3306
        "NAME": "@@dest_db_name@@",  # will be the default database; use None for no default database  # noqa
        "USER": "@@dest_db_user@@",
        "PASSWORD": "@@dest_db_password@@",
    },
    # -------------------------------------------------------------------------
    # One or more secret databases for RID/PID mapping
    # -------------------------------------------------------------------------
    "secret_1": {
        "ENGINE": "@@secret_db1_engine@@",
        "HOST": "@@secret_db1_host@@",  # e.g. 127.0.0.1
        "PORT": "@@secret_db1_port@@",
        "NAME": "@@secret_db1_name@@",
        "USER": "@@secret_db1_user@@",
        "PASSWORD": "@@secret_db1_password@@",
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
    # Optional: 'cpft_systmone'
    # ... see ClinicalDatabaseType in crate_anon/crateweb/config/constants.py
}

# Which database should be used to look up demographic details?
CLINICAL_LOOKUP_DB = "dummy_clinical"

# Which database should be used to look up consent modes?
CLINICAL_LOOKUP_CONSENT_DB = "dummy_clinical"

# Research database title (displayed in web site)
RESEARCH_DB_TITLE = "My NHS Trust Research Database"

# Database structure information for CRATE's query builders.
# See https://crateanon.readthedocs.io/en/latest/website_config/web_config_file.html  # noqa
RESEARCH_DB_INFO = [
    {
        # Unique name e.g. "myresearchdb":
        RDIKeys.NAME: "@@rdi1_name@@",
        # Human-friendly description e.g. "My friendly research database":
        RDIKeys.DESCRIPTION: "@@rdi1_description@@",
        # Database name as seen by the database engine:
        # - BLANK, i.e. "", for MySQL.
        # - BLANK, i.e. "", for PostgreSQL.
        # - The database name, for SQL Server.
        RDIKeys.DATABASE: "@@rdi1_database@@",
        # Schema name:
        # - The database=schema name, for MySQL.
        # - The schema name, for PostgreSQL (usual default: "public").
        # - The schema name, for SQL Server (usual default: "dbo").
        RDIKeys.SCHEMA: "@@rdi1_schema@@",
        # Fields not in the database, but used for SELECT AS statements for
        # some clinician views:
        # e.g. "my_pid_field":
        RDIKeys.PID_PSEUDO_FIELD: "@@rdi1_pid_psuedo_field@@",
        # e.g. "my_mpid_field":
        RDIKeys.MPID_PSEUDO_FIELD: "@@rdi1_mpid_pseudo_field@@",
        # Fields and tables found within the database:
        # e.g. "trid"
        RDIKeys.TRID_FIELD: "@@rdi1_trid_field@@",
        # e.g. "brcid"
        RDIKeys.RID_FIELD: "@@rdi1_rid_field@@",
        # e.g. 1
        RDIKeys.RID_FAMILY: @@rdi1_rid_family@@,
        # e.g. "patients"
        RDIKeys.MRID_TABLE: "@@rdi1_mrid_table@@",
        # e.g. "nhshash"
        RDIKeys.MRID_FIELD: "@@rdi1_mrid_field@@",
        # Descriptions, used for PID lookup and the like
        # e.g. "Patient ID (My ID Num; PID) for database X"
        RDIKeys.PID_DESCRIPTION: "@@rdi1_pid_description@@",
        # e.g. "Master patient ID (NHS number; MPID)"
        RDIKeys.MPID_DESCRIPTION: "@@rdi1_mpid_description@@",
        # e.g. "Research ID (RID) for database X"
        RDIKeys.RID_DESCRIPTION: "@@rdi1_rid_description@@",
        # e.g. "Master research ID (MRID)"
        RDIKeys.MRID_DESCRIPTION: "@@rdi1_mrid_description@@",
        # e.g. "Transient research ID (TRID) for database X",
        RDIKeys.TRID_DESCRIPTION: (
            "@@rdi1_trid_description@@"
        ),
        # To look up PID/RID mappings, provide a key for "secret_lookup_db"
        # that is a database alias from DATABASES:
        # e.g. "secret_1"
        RDIKeys.SECRET_LOOKUP_DB: "@@rdi1_secret_lookup_db@@",
        # For the data finder: table-specific and default date column names
        RDIKeys.DATE_FIELDS_BY_TABLE: {@@rdi1_date_fields_by_table@@},
        # e.g. ["default_date_field"]
        RDIKeys.DEFAULT_DATE_FIELDS: [@@rdi1_default_date_fields@@],
        # Column name giving time that record was updated
        # e.g. "_when_fetched_utc"
        RDIKeys.UPDATE_DATE_FIELD: "@@rdi1_update_date_field@@",
    },
    # {
    #     RDIKeys.NAME: "similar_database",
    #     RDIKeys.DESCRIPTION: "A database sharing the RID with the first",
    #     RDIKeys.DATABASE: "similar_database",
    #     RDIKeys.SCHEMA: "similar_schema",
    #     RDIKeys.TRID_FIELD: "trid",
    #     RDIKeys.RID_FIELD: "same_rid",
    #     RDIKeys.RID_FAMILY: 1,
    #     RDIKeys.MRID_TABLE: "",
    #     RDIKeys.MRID_FIELD: "",
    #     RDIKeys.PID_DESCRIPTION: "",
    #     RDIKeys.MPID_DESCRIPTION: "",
    #     RDIKeys.RID_DESCRIPTION: "",
    #     RDIKeys.MRID_DESCRIPTION: "",
    #     RDIKeys.TRID_DESCRIPTION: "",
    #     RDIKeys.SECRET_LOOKUP_DB: "",
    #     RDIKeys.DATE_FIELDS_BY_TABLE: {},
    #     RDIKeys.DEFAULT_DATE_FIELDS: [],
    #     RDIKeys.UPDATE_DATE_FIELD: "_when_fetched_utc",
    # },
    # {
    #     RDIKeys.NAME: "different_database",
    #     RDIKeys.DESCRIPTION: "A database sharing only the MRID with the first",  # noqa: E501
    #     RDIKeys.DATABASE: "different_database",
    #     RDIKeys.SCHEMA: "different_schema",
    #     RDIKeys.TRID_FIELD: "trid",
    #     RDIKeys.RID_FIELD: "different_rid",
    #     RDIKeys.RID_FAMILY: 2,
    #     RDIKeys.MRID_TABLE: "hashed_nhs_numbers",
    #     RDIKeys.MRID_FIELD: "nhshash",
    #     RDIKeys.PID_DESCRIPTION: "",
    #     RDIKeys.MPID_DESCRIPTION: "",
    #     RDIKeys.RID_DESCRIPTION: "",
    #     RDIKeys.MRID_DESCRIPTION: "",
    #     RDIKeys.TRID_DESCRIPTION: "",
    #     RDIKeys.SECRET_LOOKUP_DB: "",
    #     RDIKeys.DATE_FIELDS_BY_TABLE: {},
    #     RDIKeys.DEFAULT_DATE_FIELDS: [],
    #     RDIKeys.UPDATE_DATE_FIELD: "_when_fetched_utc",
    # },
]

# Which database (from those defined in RESEARCH_DB_INFO above) should be used
# to look up patients when contact requests are made?
# Give the 'name' attribute of one of the databases in RESEARCH_DB_INFO.
# Its secret_lookup_db will be used for the actual lookup process.
RESEARCH_DB_FOR_CONTACT_LOOKUP = "@@research_db_for_contact_lookup@@"

# Definitions of source database names in CRATE NLP tables
NLP_SOURCEDB_MAP = {"SOURCE_DATABASE": "research"}

# For the automatic query generator, we need to know the underlying SQL dialect
# Options are
# - "mysql" => MySQL
# - "mssql" => Microsoft SQL Server
RESEARCH_DB_DIALECT = "mysql"

DISABLE_DJANGO_PYODBC_AZURE_CURSOR_FETCHONE_NEXTSET = True

# =============================================================================
# Archive views
# =============================================================================
# See https://crateanon.readthedocs.io/en/latest/website_config/web_config_file.html  # noqa

# e.g. /home/somewhere/my_archive_templates
ARCHIVE_TEMPLATE_DIR = "@@archive_template_dir@@"
# e.g. /home/somewhere/my_archive_templates/cache
ARCHIVE_TEMPLATE_CACHE_DIR = "@@archive_template_cache_dir@@"
# e.g. /home/somewhere/my_archive_templates/static
ARCHIVE_STATIC_DIR = "@@archive_static_dir@@"
ARCHIVE_ROOT_TEMPLATE = "root.mako"
# e.g. /home/somewhere/my_archive_attachments
ARCHIVE_ATTACHMENT_DIR = "@@archive_attachment_dir@@"
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
# e.g. /srv/crate_filestorage
PRIVATE_FILE_STORAGE_ROOT = "@@private_file_storage_root@@"

# Serve files via Django (inefficient but useful for testing) or via Apache
# with mod_xsendfile (or other web server configured for the X-SendFile
# directive)?
XSENDFILE = False

# How big will we accept?
MAX_UPLOAD_SIZE_BYTES = mebibytes(10)


# =============================================================================
# Outgoing e-mail
# =============================================================================
# See https://crateanon.readthedocs.io/en/latest/website_config/web_config_file.html  # noqa

# -----------------------------------------------------------------------------
# General settings for sending e-mail from Django
# -----------------------------------------------------------------------------
# https://docs.djangoproject.com/en/1.8/ref/settings/#email-backend

#   default backend:
# EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
#   bugfix for servers that only support TLSv1:
# EMAIL_BACKEND = "cardinal_pythonlib.django.mail.SmtpEmailBackendTls1"

EMAIL_HOST = "smtp.somewhere.nhs.uk"
EMAIL_PORT = 587  # usually 25 (plain SMTP) or 587 (STARTTLS)
# ... see https://www.fastmail.com/help/technical/ssltlsstarttls.html
EMAIL_HOST_USER = "myuser"
EMAIL_HOST_PASSWORD = "mypassword"
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
RDBM_ADDRESS = [
    "FREEPOST SOMEWHERE_HOSPITAL RESEARCH DATABASE MANAGER"
]  # a list


# =============================================================================
# Administrators/managers to be notified of errors
# =============================================================================
# See https://crateanon.readthedocs.io/en/latest/website_config/web_config_file.html  # noqa

# Exceptions get sent to these people.
ADMINS = [
    ("Mr Administrator", "mr_admin@somewhere.domain"),
]


# =============================================================================
# PDF creation
# =============================================================================
# See https://crateanon.readthedocs.io/en/latest/website_config/web_config_file.html  # noqa
# Note that using headers/footers requires a version of wkhtmltopdf built using
# "patched Qt". See above.
# Fetch one from http://wkhtmltopdf.org/, e.g. v0.12.4 for your OS.

WKHTMLTOPDF_FILENAME = shutil.which("wkhtmltopdf")

WKHTMLTOPDF_OPTIONS = {  # dict for pdfkit
    "disable-smart-shrinking": "",  # --disable-smart-shrinking
    "dpi": "300",
    "enable-local-file-access": "",  # --enable-local-file-access
    "encoding": "UTF-8",
    "footer-spacing": "3",  # mm, from content down to top of footer
    "header-spacing": "3",  # mm, from content up to bottom of header
    "margin-bottom": "24mm",  # from paper edge up to bottom of content?
    "margin-left": "20mm",
    "margin-right": "20mm",
    "margin-top": "21mm",  # from paper edge down to top of content?
    "orientation": "portrait",
    "page-size": "A4",
}

PDF_LOGO_ABS_URL = "@@pdf_logo_abs_url@@"
# ... path on local machine, read by wkhtmltopdf
# Examples:
#   [if you're running a web server] "http://localhost/crate_logo"
#   [Linux root path] file:///home/myuser/myfile.png
#   [Windows root path] file:///c:/path/to/myfile.png

PDF_LOGO_WIDTH = "75%"
# ... must be suitable for an <img> tag, but "150mm" isn't working; "75%" is.
# ... tune this to your logo file (see PDF_LOGO_ABS_URL)

# The PDF generator also needs to be able to find the traffic-light pictures,
# on disk (not via your web site):
TRAFFIC_LIGHT_RED_ABS_URL = (
    "file:///somewhere/crate_anon/crateweb/static/red.png"
)
TRAFFIC_LIGHT_YELLOW_ABS_URL = (
    "file:///somewhere/crate_anon/crateweb/static/yellow.png"
)
TRAFFIC_LIGHT_GREEN_ABS_URL = (
    "file:///somewhere/crate_anon/crateweb/static/green.png"
)


# =============================================================================
# Consent-for-contact settings
# =============================================================================
# See https://crateanon.readthedocs.io/en/latest/website_config/web_config_file.html  # noqa

# For how long may we contact discharged patients without specific permission?
# Use 0 for "not at all".
PERMITTED_TO_CONTACT_DISCHARGED_PATIENTS_FOR_N_DAYS = 3 * 365

# Donation to charity for clinician response (regardless of the decision):
CHARITY_AMOUNT_CLINICIAN_RESPONSE = 1.0  # in local currency, e.g. GBP

# Address HTML for letter footers.
PDF_LETTER_FOOTER_ADDRESS_HTML = ""

# Ethics info for letter footers.
ETHICS_INFO = CPFTEthics2022()


# =============================================================================
# Local information links
# =============================================================================
# See https://crateanon.readthedocs.io/en/latest/website_config/web_config_file.html  # noqa

CHARITY_URL = "http://www.cpft.nhs.uk/research.htm"
CHARITY_URL_SHORT = "www.cpft.nhs.uk/research.htm"
LEAFLET_URL_CPFTRD_CLINRES_SHORT = (
    "www.cpft.nhs.uk/research.htm > CPFT Research Database"
)

ANONYMISE_API = {
    "HASH_KEY": "@@hash_key@@",
    "ALLOWLIST_FILENAMES": {},
    "DENYLIST_FILENAMES": {},
}

"""


def main() -> None:
    """
    Command-line entry point.
    """
    parser = argparse.ArgumentParser(formatter_class=RichHelpFormatter)
    parser.add_argument(
        "--leave_placeholders",
        action="store_true",
        help="Don't substitute @@ placeholders with examples",
        default=False,
    )
    args = parser.parse_args()

    if args.leave_placeholders:
        print(DEMO_CONFIG.strip())
        return

    replace_dict = {
        "archive_attachment_dir": "/home/somewhere/my_archive_attachments",
        "archive_static_dir": "/home/somewhere/my_archive_templates/static",
        "archive_template_cache_dir": "/tmp/somewhere/my_archive_template_cache",  # noqa: E501
        "archive_template_dir": "/home/somewhere/my_archive_templates",
        "broker_url": "",
        "crate_https": "True",
        "crate_install_dir": "somewhere",
        "dest_db_engine": "django.db.backends.mysql",
        "dest_db_host": "127.0.0.1",
        "dest_db_name": "anonymous_output",
        "dest_db_password": "somepassword",
        "dest_db_port": "3306",
        "dest_db_user": "researcher",
        "django_site_root_absolute_url": "http://mymachine.mydomain",
        "force_script_name": "",
        "hash_key": "aaaa CHANGE THIS! aaaa",
        "crate_db_engine": "django.db.backends.mysql",
        "crate_db_name": "crate_db",
        "crate_db_host": "127.0.0.1",
        "crate_db_password": "somepassword",
        "crate_db_port": "3306",
        "crate_db_user": "someuser",
        "pdf_logo_abs_url": "http://localhost/crate_logo",
        "private_file_storage_root": "/srv/crate_filestorage",
        "rdi1_database": "",
        "rdi1_date_fields_by_table": "",
        "rdi1_default_date_fields": '"default_date_field"',
        "rdi1_description": "My friendly research database",
        "rdi1_mpid_description": "Master patient ID (NHS number; MPID)",
        "rdi1_mpid_pseudo_field": "my_mpid_field",
        "rdi1_mrid_description": "Master research ID (MRID)",
        "rdi1_mrid_field": "nhshash",
        "rdi1_mrid_table": "patients",
        "rdi1_name": "myresearchdb",
        "rdi1_pid_description": "Patient ID (My ID Num; PID) for database X",
        "rdi1_pid_psuedo_field": "my_pid_field",
        "rdi1_rid_description": "Research ID (RID) for database X",
        "rdi1_rid_family": "1",
        "rdi1_rid_field": "brcid",
        "rdi1_schema": "dbo",
        "rdi1_secret_lookup_db": "secret_1",
        "rdi1_trid_description": "Transient research ID (TRID) for database X",
        "rdi1_trid_field": "trid",
        "rdi1_update_date_field": "_when_fetched_utc",
        "research_db_for_contact_lookup": "myresearchdb",
        "secret_db1_engine": "django.db.backends.mysql",
        "secret_db1_host": "127.0.0.1",
        "secret_db1_name": "anonymous_mapping",
        "secret_db1_password": "somepassword",
        "secret_db1_port": "3306",
        "secret_db1_user": "anonymiser_system",
        "secret_key": "aaaaaaaaaaaaaaaaaa CHANGE THIS! aaaaaaaaaaaaaaaaaa",
    }

    config = search_replace_text(DEMO_CONFIG, replace_dict)

    missing_dict = {}

    regex = r"@@([^@]*)@@"
    for match in re.finditer(regex, config):
        missing_dict[f"{match.group(1)}"] = ""

    if missing_dict:
        print(
            "@@ Placeholders not substituted in DEMO_CONFIG:", file=sys.stderr
        )
        pprint.pprint(missing_dict, stream=sys.stderr)
        sys.exit(EXIT_FAILURE)

    print(config.strip())


def search_replace_text(text: str, replace_dict: Dict[str, str]) -> str:
    for search, replace in replace_dict.items():
        if replace is None:
            print(f"Can't replace '{search}' with None")
            sys.exit(EXIT_FAILURE)

        text = text.replace(f"@@{search}@@", replace)

    return text


if __name__ == "__main__":
    main()
