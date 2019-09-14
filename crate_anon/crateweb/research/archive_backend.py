#!/usr/bin/env python

"""
crate_anon/crateweb/research/archive_backend.py

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

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

**Support functions for the archive system.**

"""

import logging
# from os import DirEntry, scandir
from os.path import abspath, getmtime, isfile, join
from typing import Any, Dict, List

from cardinal_pythonlib.fileops import mkdir_p
from django.conf import settings
from django.http.request import HttpRequest
from django.http.response import (
    HttpResponse,
    HttpResponseBadRequest,
)
from django.urls import reverse
from mako.lookup import TemplateLookup

from crate_anon.crateweb.config.constants import UrlNames, UrlKeys
from crate_anon.crateweb.core.utils import url_with_querystring
from crate_anon.crateweb.core.constants import SettingsKeys
from crate_anon.crateweb.research.models import (
    ArchiveAttachmentAudit,
    ArchiveTemplateAudit,
)

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

class ArchiveContextKeys(object):
    """
    Names of objects that become part of the context in which archive templates
    operate. Some are also used as URL parameter keys.

    The case here is to avoid confusion not to indicate "constness" within
    this class.
    """
    CRATE_HOME_URL = "CRATE_HOME_URL"
    execute = "execute"
    get_attachment_url = "get_attachment_url"
    get_patient_template_url = "get_patient_template_url"
    get_static_url = "get_static_url"
    get_template_url = "get_template_url"
    patient_id = "patient_id"
    query_params = "query_params"
    request = "request"


# For attachments: default for guess_content_type
DEFAULT_GUESS_CONTENT_TYPE = True


# =============================================================================
# Configuration-dependent quasi-constants
# =============================================================================

# Read from settings. Better to crash early than when a user asks.

_archive_attachment_dir = getattr(
    settings, SettingsKeys.ARCHIVE_ATTACHMENT_DIR, "")
_archive_root_template = getattr(
    settings, SettingsKeys.ARCHIVE_ROOT_TEMPLATE, "")
_archive_static_dir = getattr(
    settings, SettingsKeys.ARCHIVE_STATIC_DIR, "")
_archive_template_cache_dir = getattr(
    settings, SettingsKeys.ARCHIVE_TEMPLATE_CACHE_DIR, "")
_archive_template_dir = getattr(
    settings, SettingsKeys.ARCHIVE_TEMPLATE_DIR, "")

ARCHIVE_CONTEXT = getattr(
    settings, SettingsKeys.ARCHIVE_CONTEXT, {})

CACHE_CONTROL_MAX_AGE_ARCHIVE_ATTACHMENTS = getattr(
    settings, SettingsKeys.CACHE_CONTROL_MAX_AGE_ARCHIVE_ATTACHMENTS, 0)
CACHE_CONTROL_MAX_AGE_ARCHIVE_TEMPLATES = getattr(
    settings, SettingsKeys.CACHE_CONTROL_MAX_AGE_ARCHIVE_TEMPLATES, 0)
CACHE_CONTROL_MAX_AGE_ARCHIVE_STATIC = getattr(
    settings, SettingsKeys.CACHE_CONTROL_MAX_AGE_ARCHIVE_STATIC, 0)

# =============================================================================
# Configuration checks
# =============================================================================

ARCHIVE_IS_CONFIGURED = bool(
    _archive_attachment_dir and
    _archive_root_template and
    _archive_static_dir and
    _archive_template_cache_dir and
    _archive_template_dir
)


def archive_misconfigured_response() -> HttpResponse:
    """
    Returns an error :class:`HttpResponse` describing how the archive is
    misconfigured.
    """
    missing = []  # type: List[str]
    if not _archive_attachment_dir:
        missing.append(SettingsKeys.ARCHIVE_ATTACHMENT_DIR)
    if not _archive_root_template:
        missing.append(SettingsKeys.ARCHIVE_ROOT_TEMPLATE)
    if not _archive_static_dir:
        missing.append(SettingsKeys.ARCHIVE_STATIC_DIR)
    if not _archive_template_cache_dir:
        missing.append(SettingsKeys.ARCHIVE_TEMPLATE_CACHE_DIR)
    if not _archive_template_dir:
        missing.append(SettingsKeys.ARCHIVE_TEMPLATE_DIR)
    return HttpResponseBadRequest(
        f"Archive not configured. Administrator has not set: {missing!r}")


# =============================================================================
# Set up caches and Mako lookups.
# =============================================================================

if ARCHIVE_IS_CONFIGURED:
    mkdir_p(_archive_template_cache_dir)
    archive_mako_lookup = TemplateLookup(
        directories=[_archive_template_dir],
        module_directory=_archive_template_cache_dir,
        strict_undefined=True,  # raise error immediately upon typos!
    )
else:
    archive_mako_lookup = None


# =============================================================================
# Auditing
# =============================================================================

def audit_archive_template(request: HttpRequest,
                           patient_id: str, query_string: str) -> None:
    """
    Audits access to a template for a patient.

    Args:
        request:
            Django request
        patient_id:
            patient ID
        query_string:
            URL query string, which will include details of the template and
            any other arguments.
    """
    auditor = ArchiveTemplateAudit(user=request.user,
                                   patient_id=patient_id,
                                   query_string=query_string)
    auditor.save()


def audit_archive_attachment(request: HttpRequest,
                             patient_id: str, filename: str) -> None:
    """
    Audits access to an attachment via a patient's archive view.

    Args:
        request:
            Django request
        patient_id:
            patient ID
        filename:
            filename of attachment within archive
    """
    auditor = ArchiveAttachmentAudit(user=request.user,
                                     patient_id=patient_id,
                                     filename=filename)
    auditor.save()


# =============================================================================
# Generic paths
# =============================================================================

def safe_path(directory: str, filename: str) -> str:
    """
    Ensures that a filename is safe and within a directory -- for example, that
    nobody passes a filename like ``../../../etc/passwd`` to break out of our
    directory.

    Args:
        directory: directory, within which filename must be
        filename: filename

    Returns:
        str: the filename if it's safe and exists
    """
    if not directory:
        return ""
    final_filename = abspath(join(directory, filename))
    if not final_filename.startswith(directory):
        return ""
    if not isfile(final_filename):
        return ""
    return final_filename


# =============================================================================
# Archive paths
# =============================================================================

def get_archive_template_filepath(template_name: str) -> str:
    """
    Returns the full path of a template, or "" if none is found.

    Args:
        template_name: name of the template
    """
    return join(_archive_template_dir, template_name)
    # for entry in scandir(_archive_template_dir):  # type: DirEntry
    #     if entry.name == template_name:
    #         return entry.path
    # return ""


def get_archive_attachment_filepath(filename: str) -> str:
    """
    Returns the full path of an archive attachment.

    Args:
        filename: name of the attachment
    """
    return safe_path(_archive_attachment_dir, filename)


def get_archive_static_filepath(filename: str) -> str:
    """
    Returns the full path of an archive static file.

    Args:
        filename: name of the static file
    """
    return safe_path(_archive_static_dir, filename)


# =============================================================================
# Generic URL generation
# =============================================================================

def add_file_timestamp_to_url_query(filepath: str,
                                    qparams: Dict[str, Any]) -> None:
    """
    Adds a file's timestamp to the query parameters that will make up a URL.

    Why? So that if the file is edited, a new URL is generated, and caching
    browsers will automatically refresh.

    See

    - https://stackoverflow.com/questions/9692665/cache-busting-via-params
    - https://docs.python.org/3/library/os.path.html#os.path.getmtime

    Args:
        filepath: full path to file
        qparams: parameter dictionary, which will be modified
    """
    if not isfile(filepath):
        log.error(
            f"add_file_timestamp_to_url_query: nonexistent file {filepath!r}")
        return
    qparams[UrlKeys.MTIME] = str(getmtime(filepath))


# =============================================================================
# Archive URL generation
# =============================================================================

def archive_template_url(template_name: str = "", patient_id: str = "",
                         **kwargs) -> str:
    """
    Creates a URL to inspect part of the archive.

    Args:
        template_name:
            short name of the (configurable) template
        patient_id:
            patient ID
        **kwargs:
            other optional arguments, passed as URL parameters

    Returns:
        A URL.

    """
    kwargs = kwargs or {}  # type: Dict[str, Any]
    qparams = kwargs.copy()
    if template_name:
        qparams[UrlKeys.TEMPLATE] = template_name
        filepath = get_archive_template_filepath(template_name)
        add_file_timestamp_to_url_query(filepath, qparams)
    if patient_id:
        qparams[UrlKeys.PATIENT_ID] = patient_id
    # log.critical("qparams: {!r}", qparams)
    url = url_with_querystring(reverse(UrlNames.ARCHIVE_TEMPLATE), **qparams)
    # log.critical(f"archive_template_url: {url!r}")
    return url


def archive_root_url() -> str:
    """
    Returns a URL to the root of the archive, typically including the "launch
    for patient" view.
    """
    return archive_template_url(_archive_root_template)


def archive_attachment_url(
        filename: str,
        patient_id: str = "",
        content_type: str = "",
        offered_filename: str = "",
        guess_content_type: bool = None) -> str:
    """
    Returns a URL to download an archive attachment (e.g. a PDF).

    Args:
        filename:
            filename on disk, within the archive's attachment directory
        patient_id:
            patient ID (used for auditing) 
        content_type: 
            HTTP content type; see
            https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Type
        offered_filename:
            filename offered to user
        guess_content_type:
            if no content_type is specified, should we guess? Pass
            ``None`` for the default, :data:`DEFAULT_GUESS_CONTENT_TYPE`.
    """  # noqa
    qparams = {
        UrlKeys.PATIENT_ID: patient_id,
        UrlKeys.FILENAME: filename,
    }
    if content_type:
        qparams[UrlKeys.CONTENT_TYPE] = content_type
    if offered_filename:
        qparams[UrlKeys.OFFERED_FILENAME] = offered_filename
    if guess_content_type is not None:
        qparams[UrlKeys.GUESS_CONTENT_TYPE] = int(guess_content_type)
    filepath = get_archive_attachment_filepath(filename)
    add_file_timestamp_to_url_query(filepath, qparams)
    return url_with_querystring(
        reverse(UrlNames.ARCHIVE_ATTACHMENT), **qparams)


def archive_static_url(filename: str) -> str:
    """
    Returns a URL to download a static file from the archive.

    Args:
        filename:
            filename on disk, within the archive's static directory 
    """  # noqa
    qparams = {UrlKeys.FILENAME: filename}
    filepath = get_archive_static_filepath(filename)
    add_file_timestamp_to_url_query(filepath, qparams)
    return url_with_querystring(reverse(UrlNames.ARCHIVE_STATIC), **qparams)
