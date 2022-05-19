#!/usr/bin/env python

"""
crate_anon/crateweb/config/test_settings.py

===============================================================================

    Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).

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

**Django test settings for crateweb project.**

"""

from pathlib import Path

from crate_anon.crateweb.config.constants import ResearchDbInfoKeys as RDIKeys

BASE_DIR = Path(__file__).resolve().parent

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "crate_db.sqlite3",
    },
    "research": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "research.sqlite3",
    },
    "secret": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "secret.sqlite3",
    },
}

ROOT_URLCONF = "crate_anon.crateweb.config.urls"

INSTALLED_APPS = (
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",  # for nice comma formatting of numbers
    "debug_toolbar",  # for debugging
    "django_extensions",  # for graph_models, show_urls etc.
    "sslserver",  # for SSL testing
    "rest_framework",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    # 'kombu.transport.django',  # for Celery with Django database as broker
    # 'template_profiler_panel',
    # 'silk',
    "crate_anon.crateweb.config.apps.UserProfileAppConfig",  # for user-specific settings  # noqa
    "crate_anon.crateweb.config.apps.ResearchAppConfig",  # the research database query app  # noqa
    "crate_anon.crateweb.config.apps.ConsentAppConfig",  # the consent-to-contact app  # noqa
    "crate_anon.crateweb.config.apps.CoreAppConfig",  # for e.g. the runcpserver command  # noqa
    "crate_anon.crateweb.config.apps.ApiConfig",  # for the anonymisation API
)

RESEARCH_DB_DIALECT = "mysql"

RESEARCH_DB_INFO = [
    {
        RDIKeys.NAME: "research",
        RDIKeys.DESCRIPTION: "Demo research database",
        RDIKeys.DATABASE: "",
        RDIKeys.SCHEMA: "research",
        RDIKeys.PID_PSEUDO_FIELD: "pid",
        RDIKeys.MPID_PSEUDO_FIELD: "mpid",
        RDIKeys.TRID_FIELD: "trid",
        RDIKeys.RID_FIELD: "brcid",
        RDIKeys.RID_FAMILY: 1,
        RDIKeys.MRID_TABLE: "patients",
        RDIKeys.MRID_FIELD: "nhshash",
        RDIKeys.PID_DESCRIPTION: "Patient ID",
        RDIKeys.MPID_DESCRIPTION: "Master patient ID",
        RDIKeys.RID_DESCRIPTION: "Research ID",
        RDIKeys.MRID_DESCRIPTION: "Master research ID",
        RDIKeys.TRID_DESCRIPTION: "Transient research ID",
        RDIKeys.SECRET_LOOKUP_DB: "secret",
        RDIKeys.DATE_FIELDS_BY_TABLE: {},
        RDIKeys.DEFAULT_DATE_FIELDS: [],
        RDIKeys.UPDATE_DATE_FIELD: "_when_fetched_utc",
    },
]

RESEARCH_DB_FOR_CONTACT_LOOKUP = "research"

PRIVATE_FILE_STORAGE_ROOT = "/tmp/files"
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 Mb
SECRET_KEY = "ti_aghvCFNnC6L3M8Sq48n1j0SIXaITJO0uFi2DTXBc"
RESEARCH_DB_TITLE = "My NHS Trust Research Database"
FORCE_SCRIPT_NAME = "/crate"
