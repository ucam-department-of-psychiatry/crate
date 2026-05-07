"""
crate_anon/crateweb/config/docs_settings.py

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

**Django settings for crateweb project, used only when generating docs.**

"""

import os

from crate_anon.common.constants import mebibytes

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ROOT_URLCONF = "crate_anon.crateweb.config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "crate_anon.crateweb.core.context_processors.common_context",
            ],
            "loaders": [
                (
                    "django.template.loaders.cached.Loader",
                    [
                        "django.template.loaders.filesystem.Loader",
                        "django.template.loaders.app_directories.Loader",
                    ],
                ),
            ],
        },
    },
]

INSTALLED_APPS = (
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "debug_toolbar",
    "django_extensions",
    "sslserver",
    "rest_framework",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "crate_anon.crateweb.config.apps.UserProfileAppConfig",
    "crate_anon.crateweb.config.apps.ResearchAppConfig",
    "crate_anon.crateweb.config.apps.ConsentAppConfig",
    "crate_anon.crateweb.config.apps.CoreAppConfig",
    "crate_anon.crateweb.config.apps.ApiConfig",
    "crate_anon.crateweb.config.apps.NlpClassificationConfig",
)

MIDDLEWARE = (
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "cardinal_pythonlib.django.middleware.UserBasedExceptionMiddleware",
    "cardinal_pythonlib.django.middleware.LoginRequiredMiddleware",
    "crate_anon.crateweb.core.middleware.RestrictAdminMiddleware",
)

STATIC_URL = "/crate_static/"
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

REST_FRAMEWORK = {"DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema"}

SPECTACULAR_SETTINGS = {
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
    "TITLE": "CRATE API",
    "DESCRIPTION": (
        "Clinical Records Anonymisation and Text Extraction (CRATE)"
    ),
    "VERSION": "0.0.1",
}


PRIVATE_FILE_STORAGE_ROOT = "/tmp/files"
MAX_UPLOAD_SIZE_BYTES = mebibytes(10)
RESEARCH_DB_TITLE = "My NHS Trust Research Database"
FORCE_SCRIPT_NAME = "/crate"
