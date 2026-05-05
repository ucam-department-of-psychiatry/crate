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
        # 'APP_DIRS': True,  # can't use OPTIONS/loaders with this
        "OPTIONS": {
            "context_processors": [
                # 'django.template.context_processors.debug',
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "crate_anon.crateweb.core.context_processors.common_context",
            ],
            "loaders": [
                # https://docs.djangoproject.com/en/1.9/ref/templates/api/
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
    "crate_anon.crateweb.config.apps.UserProfileAppConfig",  # for user-specific settings  # noqa: E501
    "crate_anon.crateweb.config.apps.ResearchAppConfig",  # the research database query app  # noqa: E501
    "crate_anon.crateweb.config.apps.ConsentAppConfig",  # the consent-to-contact app  # noqa: E501
    "crate_anon.crateweb.config.apps.CoreAppConfig",  # for e.g. the runcpserver command  # noqa: E501
    "crate_anon.crateweb.config.apps.ApiConfig",  # for the anonymisation API
)

MIDDLEWARE = (
    # 'silk.middleware.SilkyMiddleware',
    # Last, when using the profiling panel? But actually breaks it...
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    # ... should be added automatically, but there's a problem (2016-04-14)
    # ... reinstated here 2017-01-30 (django-debug-toolbar==1.6)
    # ... "as early as possible... but after any other middle that encodes the
    #     response's content, such as GZipMiddleware"
    # ... http://django-debug-toolbar.readthedocs.io/en/1.0/installation.html#explicit-setup  # noqa: E501
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # 'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # Additional:
    "cardinal_pythonlib.django.middleware.UserBasedExceptionMiddleware",  # provide debugging details to superusers  # noqa: E501
    "cardinal_pythonlib.django.middleware.LoginRequiredMiddleware",  # prohibit all pages except login pages if not logged in  # noqa: E501
    # 'cardinal_pythonlib.django.middleware.DisableClientSideCachingMiddleware',  # no client-side caching  # noqa: E501
    "crate_anon.crateweb.core.middleware.RestrictAdminMiddleware",  # non-developers can't access the devadmin site  # noqa: E501
    # 'cardinal_pythonlib.django.request_cache.RequestCacheMiddleware',  # per-request cache, UNTESTED  # noqa: E501
)

STATIC_URL = "/crate_static/"
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

REST_FRAMEWORK = {"DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema"}

SPECTACULAR_SETTINGS = {
    "SWAGGER_UI_DIST": "SIDECAR",  # shorthand to use the sidecar instead
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
    "TITLE": "CRATE API",
    "DESCRIPTION": (
        "Clinical Records Anonymisation and Text Extraction (CRATE)"
    ),
    "VERSION": "0.0.1",  # TODO: Allow breaking changes until 1.0.0?
}


PRIVATE_FILE_STORAGE_ROOT = "/tmp/files"
MAX_UPLOAD_SIZE_BYTES = mebibytes(10)
RESEARCH_DB_TITLE = "My NHS Trust Research Database"
FORCE_SCRIPT_NAME = "/crate"
