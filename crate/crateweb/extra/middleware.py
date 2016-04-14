#!/usr/bin/env python3
# extra/middleware.py

import logging
from re import compile
import sys

from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
# from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse
from django.views.debug import technical_500_response
from django.utils.cache import add_never_cache_headers

logger = logging.getLogger(__name__)


# =============================================================================
# UserBasedExceptionMiddleware
# =============================================================================
# From p436 of Greenfield & Greenfield (2015), "Two Scoops of Django:
# Best Practices for Django 1.8".

class UserBasedExceptionMiddleware(object):
    # noinspection PyUnusedLocal
    @staticmethod
    def process_exception(request, exception):
        if request.user.is_superuser:
            return technical_500_response(request, *sys.exc_info())


# =============================================================================
# LoginRequiredMiddleware
# =============================================================================

# -----------------------------------------------------------------------------
# 1.
# -----------------------------------------------------------------------------
"""
Middleware to require login for all pages.

Copyright (C) 2008 Ryan Witt
Licensed under the Creative Commons Attribution 3.0 United States License
http://onecreativeblog.com/post/59051248/django-login-required-middleware

Modified according to: https://djangosnippets.org/snippets/2845/
"""

# EXEMPT_URLS = [compile(settings.LOGIN_URL.lstrip('/'))]
# if hasattr(settings, 'LOGIN_EXEMPT_URLS'):
#     EXEMPT_URLS += [compile(expr) for expr in settings.LOGIN_EXEMPT_URLS]
#
#
# class LoginRequiredMiddleware:
#     """
#     Middleware that requires a user to be authenticated to view any page
#     other than LOGIN_URL. Exemptions to this requirement can optionally be
#     specified in settings via a list of regular expressions in
#     LOGIN_EXEMPT_URLS (which you can copy from your urls.py).
#
#     Requires authentication middleware and template context processors to be
#     loaded. You'll get an error if they aren't.
#     """
#     def process_request(self, request):
#         assert hasattr(request, 'user'), "The Login Required middleware\
#  requires authentication middleware to be installed. Edit your\
#  MIDDLEWARE_CLASSES setting to insert\
#  'django.contrib.auth.middleware.AuthenticationMiddleware'. If that doesn't\
#  work, ensure your TEMPLATE_CONTEXT_PROCESSORS setting includes\
#  'django.core.context_processors.auth'."
#         if not request.user.is_authenticated():
#             path = request.path_info.lstrip('/')
#             if not any(m.match(path) for m in EXEMPT_URLS):
#                 # (1) Simple version:
#                 # return HttpResponseRedirect(settings.LOGIN_URL)
#                 # (2) With 'next' parameter:
#                 path = request.get_full_path()
#                 return redirect_to_login(path, settings.LOGIN_URL,
#                                          REDIRECT_FIELD_NAME)


# -----------------------------------------------------------------------------
# 2. Alternative!
# -----------------------------------------------------------------------------
# http://stackoverflow.com/questions/3214589/

# class LoginRequiredMiddleware(object):
#     """
#     For an exempt view:
#         def someview(request, *args, **kwargs):
#             # body of view
#         someview.login_required = False
#
#         class SomeView(View):
#             login_required = False
#             # body of view
#     """
#     def process_view(self, request, view_func, view_args, view_kwargs):
#         if not getattr(view_func, 'login_required', True):
#             return None  # exempt
#         return login_required(view_func)(request, *view_args, **view_kwargs)


# -----------------------------------------------------------------------------
# 3. RNC; composite of those patterns.
# -----------------------------------------------------------------------------

EXEMPT_URLS = [compile(settings.LOGIN_URL.lstrip('/'))]
if hasattr(settings, 'LOGIN_EXEMPT_URLS'):
    EXEMPT_URLS += [compile(expr.lstrip('/'))
                    for expr in settings.LOGIN_EXEMPT_URLS]


class LoginRequiredMiddleware:
    """
    Middleware that requires a user to be authenticated to view any page other
    than LOGIN_URL. Exemptions to this requirement can optionally be specified
    in settings via a list of regular expressions in LOGIN_EXEMPT_URLS (which
    you can copy from your urls.py).

    Requires authentication middleware and template context processors to be
    loaded. You'll get an error if they aren't.

    Other way of doing exemptions, for an exempt view:

        def someview(request, *args, **kwargs):
            # body of view
        someview.login_required = False

        class SomeView(View):
            login_required = False
            # body of view
    """

    # noinspection PyUnusedLocal
    @staticmethod
    def process_view(request, view_func, view_args, view_kwargs):
        if not hasattr(request, 'user'):
            raise ImproperlyConfigured(
                "The Login Required middleware requires authentication "
                "middleware to be installed. Edit your MIDDLEWARE_CLASSES "
                "setting to insert "
                "'django.contrib.auth.middleware.AuthenticationMiddleware'. "
                "If that doesn't work, ensure your "
                "TEMPLATE_CONTEXT_PROCESSORS setting includes "
                "'django.core.context_processors.auth'.")
        if request.user.is_authenticated():
            return None  # OK
        if not getattr(view_func, 'login_required', True):
            return None  # OK, exempt
        path = request.path_info.lstrip('/')
        # Path might look like 'login/' regardless of Django mount point
        if any(m.match(path) for m in EXEMPT_URLS):
            return None  # OK, exempt
        fullpath = request.get_full_path()
        return redirect_to_login(fullpath, reverse(settings.LOGIN_VIEW_NAME),
                                 REDIRECT_FIELD_NAME)


# =============================================================================
# DisableClientSideCachingMiddleware
# =============================================================================
# http://stackoverflow.com/questions/2095520/fighting-client-side-caching-in-django  # noqa

class DisableClientSideCachingMiddleware(object):
    # noinspection PyUnusedLocal
    @staticmethod
    def process_response(request, response):
        add_never_cache_headers(response)
        return response
