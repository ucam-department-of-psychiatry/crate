#!/usr/bin/env python

"""
crate_anon/crateweb/core/constants.py

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

**Core constants, like field lengths.**

"""

DJANGO_DEFAULT_CONNECTION = 'default'  # key to django.db.connections
LEN_ADDRESS = 100
LEN_FIELD_DESCRIPTION = 100
LEN_NAME = 100
LEN_PHONE = 20
LEN_TITLE = 20
MAX_HASH_LENGTH = 128
SCRUBBER_PNG_FILENAME = "scrubber.png"


class SettingsKeys(object):
    """
    Keys for the Django ``settings.py`` file -- particularly those that are
    optional, for which we use :func:`getattr`.
    """
    ARCHIVE_ATTACHMENT_DIR = "ARCHIVE_ATTACHMENT_DIR"
    ARCHIVE_CONTEXT = "ARCHIVE_CONTEXT"
    ARCHIVE_ROOT_TEMPLATE = "ARCHIVE_ROOT_TEMPLATE"
    ARCHIVE_STATIC_DIR = "ARCHIVE_STATIC_DIR"
    ARCHIVE_TEMPLATE_CACHE_DIR = "ARCHIVE_TEMPLATE_CACHE_DIR"
    ARCHIVE_TEMPLATE_DIR = "ARCHIVE_TEMPLATE_DIR"
    CACHE_CONTROL_MAX_AGE_ARCHIVE_ATTACHMENTS = "CACHE_CONTROL_MAX_AGE_ARCHIVE_ATTACHMENTS"  # noqa
    CACHE_CONTROL_MAX_AGE_ARCHIVE_STATIC = "CACHE_CONTROL_MAX_AGE_ARCHIVE_STATIC"  # noqa
    CACHE_CONTROL_MAX_AGE_ARCHIVE_TEMPLATES = "CACHE_CONTROL_MAX_AGE_ARCHIVE_TEMPLATES"  # noqa
    DISABLE_DJANGO_PYODBC_AZURE_CURSOR_FETCHONE_NEXTSET = "DISABLE_DJANGO_PYODBC_AZURE_CURSOR_FETCHONE_NEXTSET"  # noqa
    NLP_SOURCEDB_MAP = "NLP_SOURCEDB_MAP"
    VISZONE_CONTEXT = "VISZONE_CONTEXT"
    VISZONE_ROOT_TEMPLATE = "VISZONE_ROOT_TEMPLATE"
    VISZONE_STATIC_DIR = "VISZONE_STATIC_DIR"
    VISZONE_TEMPLATE_CACHE_DIR = "VISZONE_TEMPLATE_CACHE_DIR"
    VISZONE_TEMPLATE_DIR = "VISZONE_TEMPLATE_DIR"
