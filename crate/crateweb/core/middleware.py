#!/usr/bin/env python3
# core/middleware.py

from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse
from django.http import HttpResponseForbidden
from crate.crateweb.core.utils import is_developer


# =============================================================================
# RestrictAdminMiddleware
# =============================================================================
# See https://djangosnippets.org/snippets/2227/


class RestrictAdminMiddleware(object):
    """
    A middleware that restricts different admin sites depending on user
    privileges.
    """
    def process_request(self, request):
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
