#!/usr/bin/env python3
# crate_anon/crateweb/core/utils.py

import logging
import urllib.parse
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import QueryDict
from django.utils import timezone
from crate_anon.crateweb.userprofile.models import get_per_page

log = logging.getLogger(__name__)


# =============================================================================
# User tests/user profile
# =============================================================================

def is_superuser(user):
    """
    Function for user with decorator, e.g.
        @user_passes_test(is_superuser)
    """
    # https://docs.djangoproject.com/en/dev/topics/auth/default/#django.contrib.auth.decorators.user_passes_test  # noqa
    return user.is_superuser


def is_developer(user):
    if not user.is_authenticated():
        return False  # won't have a profile
    return user.profile.is_developer


# =============================================================================
# Forms
# =============================================================================

def paginate(request, all_items):
    per_page = get_per_page(request)
    paginator = Paginator(all_items, per_page)
    page = request.GET.get('page')
    try:
        items = paginator.page(page)
    except PageNotAnInteger:
        items = paginator.page(1)
    except EmptyPage:
        items = paginator.page(paginator.num_pages)
    return items


# =============================================================================
# URL creation
# =============================================================================

def url_with_querystring(path, querydict=None, **kwargs):
    """Add GET arguments to a URL from named arguments or a QueryDict."""
    if querydict is not None and not isinstance(querydict, QueryDict):
        raise ValueError("Bad querydict value")
    if querydict and kwargs:
        raise ValueError("Pass either a QueryDict or kwargs")
    if querydict:
        querystring = querydict.urlencode()
    else:
        querystring = urllib.parse.urlencode(kwargs)
    return path + '?' + querystring


def site_absolute_url(path):
    """
    Returns an absolute URL for the site, given a relative part.
    Use like:
        url = site_absolute_url(static('red.png'))
            ... determined in part by STATIC_URL.
        url = site_absolute_url(reverse('clinician_response', args=[self.id]))
            ... determined by SCRIPT_NAME or FORCE_SCRIPT_NAME
            ... which is context-dependent: see below

    We need to generate links to our site outside the request environment, e.g.
    for inclusion in e-mails, even when we're generating the e-mails offline
    via Celery. There's no easy way to do this automatically (site path
    information comes in only via requests), so we put it in the settings.

    See also:
        http://stackoverflow.com/questions/4150258/django-obtaining-the-absolute-url-without-access-to-a-request-object  # noqa
        https://fragmentsofcode.wordpress.com/2009/02/24/django-fully-qualified-url/  # noqa

    ---------------------------------------------------------------------------
    IMPORTANT
    ---------------------------------------------------------------------------
    BEWARE: reverse() will produce something different inside a request and
    outside it.
        http://stackoverflow.com/questions/32340806/django-reverse-returns-different-values-when-called-from-wsgi-or-shell  # noqa

    So the only moderately clean way of doing this is to do this in the Celery
    backend jobs, for anything that uses Django URLs (e.g. reverse) -- NOT
    necessary for anything using only static URLs (e.g. pictures in PDFs).

        from django.conf import settings
        from django.core.urlresolvers import set_script_prefix

        set_script_prefix(settings.FORCE_SCRIPT_NAME)

    But that does at least mean we can use the same method for static and
    Django URLs.
    """
    url = settings.DJANGO_SITE_ROOT_ABSOLUTE_URL + path
    log.debug("site_absolute_url: {} -> {}".format(path, url))
    return url


# =============================================================================
# Formatting
# =============================================================================

def get_friendly_date(date):
    if date is None:
        return ""
    try:
        return date.strftime("%d %B %Y")  # e.g. 03 December 2013
    except Exception as e:
        raise type(e)(str(e) + ' [value was {}]'.format(repr(date)))


def modelrepr(instance):
    """Default repr version of a Django model object, for debugging."""
    elements = []
    # noinspection PyProtectedMember
    for fieldname in [f.name for f in instance._meta.get_fields()]:
        try:
            value = repr(getattr(instance, fieldname))
        except ObjectDoesNotExist:
            value = "<RelatedObjectDoesNotExist>"
        elements.append("{}: {}".format(fieldname, value))
    return "<{} <{}>>".format(type(instance).__name__,
                              "; ".join(elements))
    # - type(instance).__name__ gives the Python class name from an instance
    # - ... as does ModelClass.__name__ but we don't have that directly here
    # - instance._meta.model_name gives a lower-case version


# =============================================================================
# Date/time
# =============================================================================

def string_time_now():
    """Returns current time in short-form ISO-8601 UTC, for filenames."""
    return timezone.now().strftime("%Y%m%dT%H%M%SZ")
