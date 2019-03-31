#!/usr/bin/env python

"""
crate_anon/crateweb/core/utils.py

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

**Core utility functions for the web interface.**

"""

import datetime
import logging
import urllib.parse
from typing import Any, List, Union

from django.conf import settings
from django.core.paginator import Paginator, EmptyPage, Page, PageNotAnInteger
from django.db.models import QuerySet
from django.http import QueryDict
from django.http.request import HttpRequest
from django.utils import timezone
from crate_anon.crateweb.userprofile.models import get_per_page

log = logging.getLogger(__name__)


# =============================================================================
# User tests/user profile
# =============================================================================

def is_superuser(user: settings.AUTH_USER_MODEL) -> bool:
    """
    Is the user a superuser?

    Function for use with a decorator, e.g.

    .. code-block:: python

        @user_passes_test(is_superuser)
        def some_view(request: HttpRequest) -> HttpResponse:
            pass

    Superuser equates to Research Database Manager.
    """
    # https://docs.djangoproject.com/en/dev/topics/auth/default/#django.contrib.auth.decorators.user_passes_test  # noqa
    return user.is_superuser


def is_developer(user: settings.AUTH_USER_MODEL) -> bool:
    """
    Is the user a developer?

    (Developers are a subset of superusers.)
    """
    if not user.is_authenticated:
        return False  # won't have a profile
    return user.profile.is_developer


def is_clinician(user: settings.AUTH_USER_MODEL) -> bool:
    """
    Is the user a clinician?
    """
    if not user.is_authenticated:
        return False  # won't have a profile
    return user.profile.is_clinician


# =============================================================================
# Forms
# =============================================================================

def paginate(request: HttpRequest,
             all_items: Union[QuerySet, List[Any]],
             per_page: int = None) -> Page:
    """
    Paginate a list or a Django QuerySet.

    Args:
        request: the :class:`django.http.request.HttpRequest`
        all_items: a list or a :class:`django.db.models.QuerySet`
        per_page: number of items per page

    Returns:
        a :class:`django.core.paginator.Page`

    """
    if per_page is None:
        per_page = get_per_page(request)
    paginator = Paginator(all_items, per_page)
    # noinspection PyCallByClass,PyArgumentList
    requested_page = request.GET.get('page')
    try:
        return paginator.page(requested_page)
    except PageNotAnInteger:
        return paginator.page(1)
    except EmptyPage:
        return paginator.page(paginator.num_pages)


# =============================================================================
# URL creation
# =============================================================================

def url_with_querystring(path: str,
                         querydict: QueryDict = None,
                         **kwargs: Any) -> str:
    """
    Add GET arguments to a URL from named arguments or a QueryDict.

    Args:
        path:
            a base URL path
        querydict:
            a :class:`django.http.QueryDict`
        **kwargs:
            as an alternative to the ``querydict``, we can use ``kwargs`` as a
            dictionary of query attribute-value pairs

    Returns:
        the URL with query parameters
    """
    if querydict is not None and not isinstance(querydict, QueryDict):
        raise ValueError("Bad querydict value")
    if querydict and kwargs:
        raise ValueError("Pass either a QueryDict or kwargs")
    if querydict:
        querystring = querydict.urlencode()
    else:
        querystring = urllib.parse.urlencode(kwargs)
    return path + '?' + querystring


def site_absolute_url(path: str) -> str:
    """
    Returns an absolute URL for the site, given a relative part.
    Use like:

    .. code-block:: python

        url = site_absolute_url(static('red.png'))
            # ... determined in part by STATIC_URL.
        url = site_absolute_url(reverse('clinician_response', args=[self.id]))
            # ... determined by SCRIPT_NAME or FORCE_SCRIPT_NAME
            # ... which is context-dependent: see below

    We need to generate links to our site outside the request environment, e.g.
    for inclusion in e-mails, even when we're generating the e-mails offline
    via Celery. There's no easy way to do this automatically (site path
    information comes in only via requests), so we put it in the settings.

    See also:

    - http://stackoverflow.com/questions/4150258/django-obtaining-the-absolute-url-without-access-to-a-request-object  # noqa
    - https://fragmentsofcode.wordpress.com/2009/02/24/django-fully-qualified-url/  # noqa

    **IMPORTANT**

    BEWARE: :func:`reverse` will produce something different inside a request
    and outside it.

    - http://stackoverflow.com/questions/32340806/django-reverse-returns-different-values-when-called-from-wsgi-or-shell  # noqa

    So the only moderately clean way of doing this is to do this in the Celery
    backend jobs, for anything that uses Django URLs (e.g. :func:`reverse`) --
    NOT necessary for anything using only static URLs (e.g. pictures in PDFs).

    .. code-block:: python

        from django.conf import settings
        from django.urls import set_script_prefix

        set_script_prefix(settings.FORCE_SCRIPT_NAME)

    But that does at least mean we can use the same method for static and
    Django URLs.
    """
    url = settings.DJANGO_SITE_ROOT_ABSOLUTE_URL + path
    log.debug(f"site_absolute_url: {path} -> {url}")
    return url


# =============================================================================
# Formatting
# =============================================================================

def get_friendly_date(date: datetime.datetime) -> str:
    """
    Returns a string form of a date/datetime.
    """
    if date is None:
        return ""
    try:
        return date.strftime("%d %B %Y")  # e.g. 03 December 2013
    except Exception as e:
        raise type(e)(str(e) + f' [value was {date!r}]')


# =============================================================================
# Date/time
# =============================================================================

def string_time_now() -> str:
    """
    Returns the current time in short-form ISO-8601 UTC, for filenames.
    """
    return timezone.now().strftime("%Y%m%dT%H%M%SZ")
