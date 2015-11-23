"""
Site-specific Django settings for CRATE web front end.
Put the secret stuff here.

SPECIMEN FILE ONLY - edit to your own requirements.
IT WILL NOT WORK until you've edited it.
"""

import os
raise Exception(
    "Well done - CRATE has found your crate_local_settings.py file at {}. "
    "However, you need to configure it for your institution's set-up, and "
    "remove this line.".format(os.path.abspath(__file__)))

# =============================================================================
# Site security
# =============================================================================

# FOR SECURITY:
# See https://docs.djangoproject.com/en/1.8/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'  # CHANGE THIS!  # noqa
# Run tools/generate_new_django_secret_key.py to generate a new one.

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False
# ... when False, note that static files must be served properly

if DEBUG:
    ALLOWED_HOSTS = []
else:
    ALLOWED_HOSTS = ['*']

# =============================================================================
# Database configuration
# =============================================================================
# https://docs.djangoproject.com/en/1.8/ref/settings/#databases

DATABASES = {
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
        'ENGINE': 'django.db.backends.mysql',
        'HOST': '127.0.0.1',
        'PORT': 3306,  # local
        'NAME': 'anonymous_output',  # will be the default schema; use None for no default schema  # noqa
        'USER': 'researcher',
        'PASSWORD': 'somepassword',
    },

    # -------------------------------------------------------------------------
    # Secret database for RID/PID mapping
    # -------------------------------------------------------------------------
    'secret': {
        'ENGINE': 'django.db.backends.mysql',
        'HOST': '127.0.0.1',
        'PORT': 3306,
        'NAME': 'anonymous_mapping',
        'USER': 'anonymiser_system',
        'PASSWORD': 'somepassword',
    },

    # Optional: 'cpft_iapt'
    # Optional: 'cpft_crs'
    # Optional: 'cpft_rio'
    # ... see keys of PATIENT_LOOKUP_DATABASES_CHOICES in core/constants.py
}

# Database title
RESEARCH_DB_TITLE = "My NHS Trust Research Database"

# Schemas to provide database structure info for
RESEARCH_DB_INFO_SCHEMAS = [
    'anonymous_output',
]

# Configuration of the secret mapping database (as set during initial
# anonymisation)
SECRET_MAP = {
    # Table within 'secret' mapping database containing PID/RID mapping
    'TABLENAME': "secret_map",
    # PID/RID fieldnames within that table
    'PID_FIELD': "patient_id",
    'RID_FIELD': "brcid",
    'MASTER_PID_FIELD': "nhsnum",
    'MASTER_RID_FIELD': "nhshash",
    'TRID_FIELD': 'trid',
    # Maximum length of the RID fields (containing a hash in a VARCHAR field)
    'MAX_RID_LENGTH': 255,
}

# Which of the databases defined above should be used for lookups?
# Must (a) be a key of PatientLookup.DATABASES_CHOICES in consent/models.py;
#      (b) be defined in DATABASES, above, UNLESS it is 'dummy_clinical'
CLINICAL_LOOKUP_DB = 'dummy_clinical'

# =============================================================================
# Local file storage (for PDFs etc).
# =============================================================================

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
# General settings for sending e-mail from Django
# https://docs.djangoproject.com/en/1.8/ref/settings/#email-backend

EMAIL_HOST = 'smtp.somewhere.nhs.uk'
EMAIL_PORT = '587'
EMAIL_HOST_USER = 'myuser'
EMAIL_HOST_PASSWORD = 'mypassword'
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False

# Who will the e-mails appear to come from?
EMAIL_SENDER = "My NHS Trust Research Database - DO NOT REPLY <noreply@somewhere.nhs.uk>"  # noqa

# During development, we route all consent-related e-mails to the developer.
# Switch SAFETY_CATCH_ON to False for production mode.
SAFETY_CATCH_ON = True
DEVELOPER_EMAIL = "testuser@somewhere.nhs.uk"

VALID_RESEARCHER_EMAIL_DOMAINS = []
# ... if empty, no checks are performed (any address is accepted)

# =============================================================================
# Research Database Manager (RDBM) details
# =============================================================================

RDBM_NAME = "John Doe"
RDBM_TITLE = "Research Database Manager"
RDBM_TELEPHONE = "01223-XXXXXX"
RDBM_EMAIL = "research.database@somewhere.nhs.uk"
RDBM_ADDRESS = ["FREEPOST SOMEWHERE_HOSPITAL RESEARCH DATABASE MANAGER"]  # a list  # noqa

# =============================================================================
# Administrators/managers to be notified of errors
# =============================================================================

# Exceptions get sent to these people.
ADMINS = (
    ('Mr Administrator', 'mr_admin@somewhere.domain'),
)

# Broken links get sent to these people
SEND_BROKEN_LINK_EMAILS = True
MANAGERS = (
    ('Mr Administrator', 'mr_admin@somewhere.domain'),
)

# =============================================================================
# PDF creation
# =============================================================================
# WKHTMLTOPDF_FILENAME: for the pdfkit PDF engine, specify a filename for
# wkhtmltopdf that incorporates any need for an X Server (not the default
# /usr/bin/wkhtmltopdf). See http://stackoverflow.com/questions/9604625/ .
# Basically, you can try
#   WKHTMLTOPDF_FILENAME =
# and if it fails, try
#   WKHTMLTOPDF_FILENAME = '/usr/bin/wkhtmltopdf'
# but if that fails, use
#   WKHTMLTOPDF_FILENAME = '/path/to/wkhtmltopdf.sh'
# where wkhtmltopdf.sh is an executable script (chmod a+x ...) containing:
#   #!/bin/bash
#   xvfb-run --auto-servernum --server-args="-screen 0 640x480x16" \
#       /usr/bin/wkhtmltopdf "$@"

WKHTMLTOPDF_FILENAME = ''
# WKHTMLTOPDF_FILENAME = '/usr/bin/wkhtmltopdf'

PDF_LOGO_ABSPATH = '/home/rudolf/Documents/code/cpft-rd-consent/logo_cpft.png'
# ... path on local machine, read by wkhtmltopdf
PDF_LOGO_WIDTH = "75%"
# ... must be suitable for an <img> tag, but "150mm" isn't working; "75%" is.

# =============================================================================
# Donations to charity
# =============================================================================

CHARITY_AMOUNT_CLINICIAN_RESPONSE = 1.0  # in local currency, e.g. GBP

# =============================================================================
# Local information links
# =============================================================================

CHARITY_URL = "http://www.cpft.nhs.uk/research.htm"
CHARITY_URL_SHORT = "www.cpft.nhs.uk/research.htm"
LEAFLET_URL_CPFTRD_CLINRES_SHORT = "www.cpft.nhs.uk/research.htm > CPFT Research Database"  # noqa
PUBLIC_RESEARCH_URL_SHORT = "www.cpft.nhs.uk/research.htm"

DJANGO_SITE_ROOT_ABSOLUTE_URL = "http://mymachine.mydomain/crate"  # example for Apache  # noqa
# DJANGO_SITE_ROOT_ABSOLUTE_URL = "http://localhost:8000"  # for the Django dev server  # noqa
