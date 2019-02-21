#!/usr/bin/env python

"""
crate_anon/crateweb/userprofile/views.py

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

**View to edit an extended user profile.**

"""

from django.http.response import HttpResponse
from django.http.request import HttpRequest
from django.shortcuts import redirect, render
from crate_anon.crateweb.userprofile.forms import UserProfileForm


# =============================================================================
# User profile settings
# =============================================================================
# http://www.slideshare.net/pydanny/advanced-django-forms-usage
# ... e.g. slide 72

def edit_profile(request: HttpRequest) -> HttpResponse:
    """
    View to edit an extended user profile.

    Args:
        request: the :class:`django.http.request.HttpRequest`

    Returns:
        a :class:`django.http.response.HttpResponse`

    """
    profile = request.user.profile
    form = UserProfileForm(request.POST if request.method == 'POST' else None,
                           instance=profile)
    if form.is_valid():
        profile = form.save()
        profile.save()
        return redirect('home')
    return render(request, 'edit_profile.html',
                  {'form': form, 'profile': profile})
