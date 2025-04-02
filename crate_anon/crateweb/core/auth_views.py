"""
crate_anon/crateweb/core/auth_views.py

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

**Authentication views.**

"""

import logging
from urllib.parse import quote_plus

from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.http import HttpResponse, HttpResponseRedirect
from django.http.request import HttpRequest
from django.shortcuts import redirect, render
from django.urls import reverse

from crate_anon.crateweb.config.constants import UrlNames, UrlKeys

log = logging.getLogger(__name__)


def login_view(request: HttpRequest) -> HttpResponse:
    """
    Main login view.
    """
    # don't call it login (name clash with django.contrib.auth.login)
    # https://www.fir3net.com/Web-Development/Django/django.html
    # http://www.flagonwiththedragon.com/2011/06/16/django-authenticationform-for-user-login/  # noqa: E501
    # https://stackoverflow.com/questions/16750464/django-redirect-after-login-not-working-next-not-posting  # noqa: E501

    # Where to after a successful login?
    # noinspection PyCallByClass,PyTypeChecker
    nextpage = request.GET.get(UrlKeys.NEXT, reverse(UrlNames.HOME))
    nextpage_quoted = quote_plus(nextpage)
    # log.debug(f"login_view: nextpage: {nextpage}")
    # log.debug(f"login_view: nextpage_quoted: {nextpage_quoted}")

    if request.user.is_authenticated:
        # Authenticated, en route somewhere else.
        return HttpResponseRedirect(nextpage)
    # Otherwise, not authenticated. Offer an authentication form.
    form = AuthenticationForm(
        None, request.POST if request.method == "POST" else None
    )
    if form.is_valid():
        # ... the form handles a bunch of user validation
        login(request, form.get_user())
        return HttpResponseRedirect(nextpage)
    return render(
        request,
        "login.html",
        {
            "form": form,
            "next": nextpage_quoted,
        },
    )


def logout_view(request: HttpRequest) -> HttpResponse:
    """
    "You have logged out" view.
    """
    logout(request)
    return render(request, "logged_out.html")


def password_change(request: HttpRequest) -> HttpResponse:
    """
    View to change your password.
    """
    # https://docs.djangoproject.com/en/1.8/topics/auth/default/#module-django.contrib.auth.forms  # noqa: E501
    form = PasswordChangeForm(
        data=request.POST if request.method == "POST" else None,
        user=request.user,
    )
    if form.is_valid():
        form.save()
        update_session_auth_hash(request, form.user)
        # ... so the user isn't immediately logged out
        return redirect(UrlNames.HOME)
    return render(request, "password_change.html", {"form": form})


# No password_reset function yet (would use PasswordResetForm)
# ... that's to reset forgotten passwords.
