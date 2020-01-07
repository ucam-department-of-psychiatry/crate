#!/usr/bin/env python

"""
crate_anon/crateweb/config/constants.py

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

**Configuration constants for the CRATE web interface.**

"""

CRATEWEB_CONFIG_ENV_VAR = 'CRATE_WEB_LOCAL_SETTINGS'
CHERRYPY_EXTRA_ARGS_ENV_VAR = 'CRATE_CHERRYPY_ARGS'
CRATEWEB_CELERY_APP_NAME = 'crate_anon.crateweb.consent'


class ResearchDbInfoKeys(object):
    """
    Keys for each dictionary within ``settings.RESEARCH_DB_INFO``, representing
    a description of a research database that CRATE will provide a view on.
    """
    NAME = 'name'
    DESCRIPTION = 'description'

    DATABASE = 'database'
    SCHEMA = 'schema'

    PID_PSEUDO_FIELD = 'pid_pseudo_field'
    MPID_PSEUDO_FIELD = 'mpid_pseudo_field'
    TRID_FIELD = 'trid_field'
    RID_FIELD = 'rid_field'
    RID_FAMILY = 'rid_family'
    MRID_TABLE = 'mrid_table'
    MRID_FIELD = 'mrid_field'

    PID_DESCRIPTION = 'pid_description'
    MPID_DESCRIPTION = 'mpid_description'
    RID_DESCRIPTION = 'rid_description'
    MRID_DESCRIPTION = 'mrid_description'
    TRID_DESCRIPTION = 'trid_description'

    SECRET_LOOKUP_DB = 'secret_lookup_db'

    DATE_FIELDS_BY_TABLE = 'date_fields_by_table'
    DEFAULT_DATE_FIELDS = 'default_date_fields'
    UPDATE_DATE_FIELD = 'update_date_field'


SOURCE_DB_NAME_MAX_LENGTH = 20


class ClinicalDatabaseType(object):
    """
    Possible source clinical database types that CRATE knows about, and can
    look up patient details for the consent-to-contact system.
    """
    # NB the following strings mustn't be longer than SOURCE_DB_NAME_MAX_LENGTH
    DUMMY_CLINICAL = 'dummy_clinical'
    CPFT_CRS = 'cpft_crs'
    CPFT_PCMIS = 'cpft_pcmis'
    CPFT_RIO_CRATE_PREPROCESSED = 'cpft_rio_crate'
    CPFT_RIO_DATAMART = 'cpft_rio_datamart'
    CPFT_RIO_RAW = 'cpft_rio_raw'
    CPFT_RIO_RCEP = 'cpft_rio_rcep'

    # For Django fields, using the above:
    DATABASE_CHOICES = (
        # First key must match a database entry in Django local settings.
        (DUMMY_CLINICAL,
         'Dummy clinical database for testing'),
        # (ClinicalDatabaseType.CPFT_PCMIS,
        #  'CPFT Psychological Wellbeing Service (IAPT) PC-MIS'),
        (CPFT_CRS,
         'CPFT Care Records System (CRS) 2005-2012'),
        (CPFT_RIO_RCEP,
         'CPFT RiO 2013- (preprocessed by Servelec RCEP tool)'),
        (CPFT_RIO_RAW,
         'CPFT RiO 2013- (raw)'),
        (CPFT_RIO_CRATE_PREPROCESSED,
         'CPFT RiO 2013- (preprocessed by CRATE)'),
        (CPFT_RIO_DATAMART,
         'CPFT RiO 2013- (data warehouse processed version)'),
    )


# Special URL for a situation not amenable to reverse():
DOWNLOAD_PRIVATESTORAGE_URL_STEM = "download_privatestorage"


class UrlNames(object):
    r"""
    Strings used as Django names for CRATE views; see
    :mod:`crate_anon.crateweb.config.urls`.

    We should use this lookup method throughout the Python code, e.g. for calls
    to :func:`reverse` and :func:`redirect`.

    We could also use them in the templates, rather than using hard-coded
    strings. We can do that via our common context,
    :func:`crate_anon.crateweb.core.context_processors.common_context`.
    However, the (runtime) failure message then becomes e.g.

    .. code-block:: none

        Reverse for '' not found. '' is not a valid view function or pattern
        name.

    rather than the more informative

    .. code-block:: none

        Reverse for 'ridlookup2' not found. 'ridlookup2' is not a valid view
        function or pattern name.

    ... so probably best not to (there is also no PyCharm checking of the
    Django context).
    """
    # Login, auth
    LOGIN = "login"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"

    # Home, about
    HOME = "home"
    ABOUT = "about"

    # Main query views
    ACTIVATE_HIGHLIGHT = "activate_highlight"
    ACTIVATE_QUERY = "activate_query"
    BUILD_QUERY = "build_query"
    COUNT = "count"
    DEACTIVATE_HIGHLIGHT = "deactivate_highlight"
    DELETE_HIGHLIGHT = "delete_highlight"
    DELETE_QUERY = "delete_query"
    DELETE_SITEWIDE_QUERY = "delete_sitewide_query"
    EDIT_DISPLAY = "edit_display"
    HIGHLIGHT = "highlight"
    PROCESS_STANDARD_QUERY = "process_standard_query"
    QUERY = "query"
    QUERY_EXCEL = "query_excel"
    RESULTS = "results"
    RESULTS_RECORDWISE = "results_recordwise"
    SAVE_DISPLAY = "save_display"
    SHOW_QUERY = "show_query"
    SITEWIDE_QUERIES = "sitewide_queries"
    SRCINFO = "srcinfo"
    STANDARD_QUERIES = "standard_queries"
    TSV = "tsv"

    # Patient Explorer views
    PE_ACTIVATE = "pe_activate"
    PE_BUILD = "pe_build"
    PE_CHOOSE = "pe_choose"
    PE_DELETE = "pe_delete"
    PE_DF_EXCEL = "pe_df_excel"
    PE_DF_RESULTS = "pe_df_results"
    PE_EDIT = "pe_edit"
    PE_EXCEL = "pe_excel"
    PE_MONSTER_RESULTS = "pe_monster_results"
    PE_ONE_TABLE = "pe_one_table"
    PE_RESULTS = "pe_results"
    PE_TABLE_BROWSER = "pe_table_browser"

    # Structure
    STRUCTURE_EXCEL = "structure_excel"
    STRUCTURE_HELP = "structure_help"
    STRUCTURE_TABLE_LONG = "structure_table_long"
    STRUCTURE_TABLE_PAGINATED = "structure_table_paginated"
    STRUCTURE_TREE = "structure_tree"
    STRUCTURE_TSV = "structure_tsv"

    # SQL helpers
    SQLHELPER_DRUG_TYPE = "sqlhelper_drug_type"
    SQLHELPER_DRUG_TYPE_WITH_DB = "sqlhelper_drug_type_with_db"
    SQLHELPER_TEXT_ANYWHERE = "sqlhelper_text_anywhere"
    SQLHELPER_TEXT_ANYWHERE_WITH_DB = "sqlhelper_text_anywhere_with_db"

    # Consent for contact
    SUBMIT_CONTACT_REQUEST = "submit_contact_request"

    # Clinician views
    ALL_TEXT_FROM_PID = "all_text_from_pid"
    ALL_TEXT_FROM_PID_WITH_DB = "all_text_from_pid_with_db"
    CLINICIAN_CONTACT_REQUEST = "clinician_contact_request"

    # Archive views
    ARCHIVE_ATTACHMENT = "archive_attachment"
    ARCHIVE_STATIC = "archive_static"
    ARCHIVE_TEMPLATE = "archive_template"
    LAUNCH_ARCHIVE = "launch_archive"

    # Look up PID/RID
    PIDLOOKUP = "pidlookup"
    PIDLOOKUP_WITH_DB = "pidlookup_with_db"
    RIDLOOKUP = "ridlookup"
    RIDLOOKUP_WITH_DB = "ridlookup_with_db"

    # User profile
    EDIT_PROFILE = "edit_profile"

    # Superuser
    CHARITY_REPORT = "charity_report"
    DOWNLOAD_PRIVATESTORAGE = "download_privatestorage"
    EXCLUSION_REPORT = "exclusion_report"
    TEST_EMAIL_RDBM = "test_email_rdbm"

    # Public views
    LEAFLET = "leaflet"
    STUDY_DETAILS = "study_details"
    STUDY_FORM = "study_form"
    STUDY_PACK = "study_pack"

    # Restricted C4C views for clinicians
    CLINICIAN_PACK = "clinician_pack"
    CLINICIAN_RESPONSE = "clinician_response"

    # Restricted views; superuser + researchers
    LETTER = "letter"
    VIEW_EMAIL_ATTACHMENT = "view_email_attachment"
    VIEW_EMAIL_HTML = "view_email_html"

    # Developer functions and test views
    DECISION_FORM_TO_PT_RE_STUDY = "decision_form_to_pt_re_study"
    DRAFT_APPROVAL_EMAIL = "draft_approval_email"
    DRAFT_APPROVAL_LETTER = "draft_approval_letter"
    DRAFT_CLINICIAN_EMAIL = "draft_clinician_email"
    DRAFT_CONFIRM_TRAFFIC_LIGHT_LETTER = "draft_confirm_traffic_light_letter"
    DRAFT_FIRST_TRAFFIC_LIGHT_LETTER = "draft_first_traffic_light_letter"
    DRAFT_LETTER_CLINICIAN_TO_PT_RE_STUDY = "draft_letter_clinician_to_pt_re_study"  # noqa
    DRAFT_TRAFFIC_LIGHT_DECISION_FORM = "draft_traffic_light_decision_form"
    DRAFT_WITHDRAWAL_EMAIL = "draft_withdrawal_email"
    DRAFT_WITHDRAWAL_LETTER = "draft_withdrawal_letter"
    GENERATE_RANDOM_NHS = "generate_random_nhs"
    TEST_CONSENT_LOOKUP = "test_consent_lookup"
    TEST_PATIENT_LOOKUP = "test_patient_lookup"


class AdminSiteNames(object):
    DEVADMIN = "devadmin"
    MGRADMIN = "mgradmin"
    RESADMIN = "resadmin"


class UrlKeys(object):
    """
    Keys used in GET parameters as part of a query string:
    ```...path?a=1&b=2``, etc.
    """
    # Generic
    NEXT = "next"
    # ... used for login redirectionmust match
    # django.contrib.auth.REDIRECT_FIELD_NAME

    # Archive system:
    CONTENT_TYPE = "content_type"  # used for attachments
    FILENAME = "filename"  # used for attachments and static files
    GUESS_CONTENT_TYPE = "guess_content_type"  # used for attachments; 0 or 1
    MTIME = "mtime"  # file modification time, from os.path.getmtime()
    PATIENT_ID = "patient_id"  # used for attachments and templates
    OFFERED_FILENAME = "offered_filename"  # used for attachments
    TEMPLATE = "template"  # used for templates
