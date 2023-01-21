#!/usr/bin/env python

"""
crate_anon/common/constants.py

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

**Constants used throughout CRATE.**

"""

import os


# =============================================================================
# Plain constants
# =============================================================================

CRATE_DOCS_URL = "https://crateanon.readthedocs.io/"

DEMO_NLP_INPUT_TERMINATOR = "STOP"
DEMO_NLP_OUTPUT_TERMINATOR = "END_OF_NLP_OUTPUT_RECORD"

EXIT_FAILURE = 1
EXIT_SUCCESS = 0

JSON_INDENT = 4

JSON_SEPARATORS_COMPACT = (",", ":")
# ... see https://docs.python.org/3/library/json.html

LOWER_CASE_STRINGS_MEANING_TRUE = ["true", "1", "t", "y", "yes"]

# Is this program running on readthedocs.org?
ON_READTHEDOCS = os.environ.get("READTHEDOCS") == "True"


# =============================================================================
# Directories within CRATE
# =============================================================================


class CratePath:
    """
    Directories within the CRATE Python package.
    """

    CRATE_ANON_DIR = os.path.abspath(
        os.path.join(
            os.path.dirname(
                os.path.abspath(__file__)
            ),  # this directory, common
            os.pardir,  # parent, crate_anon
        )
    )
    NLP_MANAGER_DIR = os.path.join(CRATE_ANON_DIR, "nlp_manager")
    JAVA_CLASSES_DIR = os.path.join(NLP_MANAGER_DIR, "compiled_nlp_classes")
    NLPRP_DIR = os.path.join(CRATE_ANON_DIR, "nlprp")


# =============================================================================
# DockerConstants
# =============================================================================


class DockerConstants:
    """
    Constants for the Docker environment.
    """

    # Directories
    DOCKER_CRATE_ROOT_DIR = "/crate"
    CONFIG_DIR = os.path.join(DOCKER_CRATE_ROOT_DIR, "cfg")
    TMP_DIR = os.path.join(DOCKER_CRATE_ROOT_DIR, "tmp")
    VENV_DIR = os.path.join(DOCKER_CRATE_ROOT_DIR, "venv")

    HOST = "0.0.0.0"
    # ... not "localhost" or "127.0.0.1"; see
    # https://nickjanetakis.com/blog/docker-tip-54-fixing-connection-reset-by-peer-or-similar-errors  # noqa


# =============================================================================
# Environment variables
# =============================================================================


class EnvVar:
    """
    Environment variable names.
    """

    CRATE_GATE_PLUGIN_FILE = "CRATE_GATE_PLUGIN_FILE"
    # ... environment variable whose presence shows that we are generating
    # docs.
    GATE_HOME = "GATE_HOME"
    GENERATING_CRATE_DOCS = "GENERATING_CRATE_DOCS"
    JAVA_HOME = "JAVA_HOME"
    KCL_KCONNECT_DIR = "KCL_KCONNECT_DIR"
    KCL_LEWY_BODY_DIAGNOSIS_DIR = "KCL_LEWY_BODY_DIAGNOSIS_DIR"
    KCL_PHARMACOTHERAPY_DIR = "KCL_PHARMACOTHERAPY_DIR"
    MEDEX_HOME = "MEDEX_HOME"
    PATH = "PATH"
    RUNNING_TESTS = "RUNNING_TESTS"
    RUN_WITHOUT_CONFIG = "CRATE_RUN_WITHOUT_LOCAL_SETTINGS"


# =============================================================================
# CRATE top-level commands
# =============================================================================


class CrateCommand:
    """
    Top-level commands within CRATE, recorded here to ensure consistency.
    However, see also crate/installer/installer.py, which duplicates some
    (because the full Python environment is not then available).
    """

    # Preprocessing
    FETCH_WORDLISTS = "crate_fetch_wordlists"
    POSTCODES = "crate_postcodes"
    PREPROCESS_PCMIS = "crate_preprocess_pcmis"
    PREPROCESS_RIO = "crate_preprocess_rio"
    PREPROCESS_SYSTMONE = "crate_preprocess_systmone"

    # Linkage
    BULK_HASH = "crate_bulk_hash"
    FUZZY_ID_MATCH = "crate_fuzzy_id_match"

    # Anonymisation
    ANON_CHECK_TEXT_EXTRACTOR = "crate_anon_check_text_extractor"
    ANON_DEMO_CONFIG = "crate_anon_demo_config"
    ANON_DRAFT_DD = "crate_anon_draft_dd"
    ANON_SHOW_COUNTS = "crate_anon_show_counts"
    ANON_SUMMARIZE_DD = "crate_anon_summarize_dd"
    ANONYMISE = "crate_anonymise"
    ANONYMISE_MULTIPROCESS = "crate_anonymise_multiprocess"
    MAKE_DEMO_DATABASE = "crate_make_demo_database"
    TEST_ANONYMISATION = "crate_test_anonymisation"
    TEST_EXTRACT_TEXT = "crate_test_extract_text"

    # NLP
    NLP = "crate_nlp"
    NLP_BUILD_GATE_JAVA_INTERFACE = "crate_nlp_build_gate_java_interface"
    NLP_BUILD_MEDEX_ITSELF = "crate_nlp_build_medex_itself"
    NLP_BUILD_MEDEX_JAVA_INTERFACE = "crate_nlp_build_medex_java_interface"
    NLP_MULTIPROCESS = "crate_nlp_multiprocess"
    NLP_PREPARE_YMLS_FOR_BIOYODIE = "crate_nlp_prepare_ymls_for_bioyodie"
    RUN_CRATE_NLP_DEMO = "crate_run_crate_nlp_demo"
    RUN_GATE_ANNIE_DEMO = "crate_run_gate_annie_demo"
    RUN_GATE_KCL_KCONNECT_DEMO = "crate_run_gate_kcl_kconnect_demo"
    RUN_GATE_KCL_LEWY_DEMO = "crate_run_gate_kcl_lewy_demo"
    RUN_GATE_KCL_PHARMACOTHERAPY_DEMO = (
        "crate_run_gate_kcl_pharmacotherapy_demo"
    )
    SHOW_CRATE_GATE_PIPELINE_OPTIONS = "crate_show_crate_gate_pipeline_options"
    SHOW_CRATE_MEDEX_PIPELINE_OPTIONS = (
        "crate_show_crate_medex_pipeline_options"
    )

    # Web site
    CELERY_STATUS = "crate_celery_status"
    DJANGO_MANAGE = "crate_django_manage"
    EMAIL_RDBM = "crate_email_rdbm"
    GENERATE_NEW_DJANGO_SECRET_KEY = "crate_generate_new_django_secret_key"
    LAUNCH_CELERY = "crate_launch_celery"
    LAUNCH_FLOWER = "crate_launch_flower"
    PRINT_DEMO_CRATEWEB_CONFIG = "crate_print_demo_crateweb_config"
    WINDOWS_SERVICE = "crate_windows_service"
    LAUNCH_CHERRYPY_SERVER = "crate_launch_cherrypy_server"
    LAUNCH_DJANGO_SERVER = "crate_launch_django_server"

    # NLP web server
    NLP_WEBSERVER_GENERATE_ENCRYPTION_KEY = (
        "crate_nlp_webserver_generate_encryption_key"  # noqa: E501
    )
    NLP_WEBSERVER_INITIALIZE_DB = "crate_nlp_webserver_initialize_db"
    NLP_WEBSERVER_LAUNCH_CELERY = "crate_nlp_webserver_launch_celery"
    NLP_WEBSERVER_LAUNCH_FLOWER = "crate_nlp_webserver_launch_flower"
    NLP_WEBSERVER_LAUNCH_GUNICORN = "crate_nlp_webserver_launch_gunicorn"
    NLP_WEBSERVER_MANAGE_USERS = "crate_nlp_webserver_manage_users"
    NLP_WEBSERVER_PRINT_DEMO = "crate_nlp_webserver_print_demo"
    NLP_WEBSERVER_PSERVE = "crate_nlp_webserver_pserve"


# =============================================================================
# HelpUrl
# =============================================================================


class HelpUrl:
    """
    Makes help URLs, for an approximation to context-sensitive help within the
    web site.

    Note that in Django's template syntax,

    .. code-block:: none

        {{ HelpUrl.main }}

    gets translated to

    .. code-block:: python

        HelpUrl.main()

    i.e. further brackets are unnecessary (and an error). See:

    - https://docs.djangoproject.com/en/2.2/topics/templates/#variables

    ... "If a variable resolves to a callable, the template system will call it
    with no arguments and use its result instead of the callable."

    """  # noqa

    @staticmethod
    def make_url(
        location: str, language: str = "en", version: str = "latest"
    ) -> str:
        """
        Make a CRATE help URL.

        Args:
            location: location within docs
            language: language (default ``en``)
            version: version (default ``latest``)
        """
        return f"{CRATE_DOCS_URL}{language}/{version}/{location}"

    @classmethod
    def main(cls) -> str:
        return cls.make_url("")

    @classmethod
    def website(cls) -> str:
        return cls.make_url("website_using/index.html")

    @classmethod
    def find_text_anywhere(cls) -> str:
        return cls.make_url(
            "website_using/clinician_privileged.html#clinician-privileged-find-text-anywhere"  # noqa: E501
        )

    @classmethod
    def clinician_lookup_rid(cls) -> str:
        return cls.make_url(
            "website_using/clinician_privileged.html#look-up-research-id-from-patient-id"  # noqa: E501
        )

    @classmethod
    def clinician_submit_contact_request(cls) -> str:
        return cls.make_url(
            "website_using/clinician_privileged.html#submit-patient-contact-request"  # noqa: E501
        )

    @classmethod
    def querybuilder(cls) -> str:
        return cls.make_url(
            "website_using/research_queries.html#query-builder"
        )

    @classmethod
    def sql(cls) -> str:
        return cls.make_url(
            "website_using/research_queries.html#research-query-sql"
        )

    @classmethod
    def highlighting(cls) -> str:
        return cls.make_url(
            "website_using/research_queries.html#highlighting-text-in-results"
        )

    @classmethod
    def results(cls) -> str:
        return cls.make_url(
            "website_using/research_queries.html#results-table-view"
        )

    @classmethod
    def patient_explorer(cls) -> str:
        return cls.make_url("website_using/patient_explorer.html")

    @classmethod
    def sqlhelper_find_text_anywhere(cls) -> str:
        return cls.make_url(
            "website_using/sql_helpers.html#find-text-anywhere"
        )

    @classmethod
    def sqlhelper_find_drugs_anywhere(cls) -> str:
        return cls.make_url(
            "website_using/sql_helpers.html#find-drugs-of-a-given-type-anywhere"  # noqa: E501
        )

    @classmethod
    def sitewide_queries(cls) -> str:
        return cls.make_url("website_using/site_queries.html")

    @classmethod
    def research_db_structure(cls) -> str:
        return cls.make_url("website_using/database_structure.html")

    @classmethod
    def submit_contact_request(cls) -> str:
        return cls.make_url(
            "website_using/contact_patients.html#submit-a-contact-request"
        )

    @classmethod
    def rdbm(cls) -> str:
        return cls.make_url("website_using/rdbm_admin.html")

    @classmethod
    def developer(cls) -> str:
        return cls.make_url("website_using/developer_admin.html")

    @classmethod
    def user_settings(cls) -> str:
        return cls.make_url(
            "website_using/clinician_researcher_overview.html#your-settings"
        )

    @classmethod
    def about_crate(cls) -> str:
        return cls.make_url(
            "website_using/clinician_researcher_overview.html#about-crate"
        )

    @classmethod
    def archive(cls) -> str:
        return cls.make_url("website_using/archive.html")


# =============================================================================
# More plain constants
# =============================================================================

# Will we run without a config file?
RUNNING_WITHOUT_CONFIG = ON_READTHEDOCS or (
    EnvVar.RUN_WITHOUT_CONFIG in os.environ
    and os.environ[EnvVar.RUN_WITHOUT_CONFIG].lower()
    in LOWER_CASE_STRINGS_MEANING_TRUE
)
