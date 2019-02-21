#!/usr/bin/env python

"""
crate_anon/crateweb/core/middleware.py

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

**Middleware.**

"""

from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse, HttpResponseForbidden, HttpRequest
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin

from crate_anon.crateweb.core.utils import is_developer


# =============================================================================
# RestrictAdminMiddleware
# =============================================================================
# See https://djangosnippets.org/snippets/2227/


class RestrictAdminMiddleware(MiddlewareMixin):
    """
    A middleware that restricts the different admin sites depending on user
    privileges.
    """
    @staticmethod
    def process_request(request: HttpRequest) -> HttpResponse:
        if not hasattr(request, 'user'):
            raise ImproperlyConfigured(
                "Authentication middleware required. Edit your"
                " MIDDLEWARE_CLASSES setting to insert"
                " 'django.contrib.auth.middleware.AuthenticationMiddleware'"
                " before the RestrictDevAdminMiddleware class.")
        if request.path.startswith(reverse('devadmin:index')):
            if not is_developer(request.user):
                return HttpResponseForbidden(
                    "Non-developers cannot access the devadmin")
        if request.path.startswith(reverse('mgradmin:index')):
            if not request.user.is_superuser:
                return HttpResponseForbidden(
                    "Non-superusers cannot access the mgradmin")
        # Django requires the staff flag for any admin.
