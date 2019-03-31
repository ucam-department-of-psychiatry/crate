#!/usr/bin/env python

"""
crate_anon/crateweb/core/views.py

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

**A few core views, like the home page.**

"""

import logging
from django.conf import settings
from django.http import HttpResponse
from django.http.request import HttpRequest
from django.shortcuts import render
from crate_anon.crateweb.core.utils import is_clinician, is_developer
from crate_anon.crateweb.research.views import query_context
from crate_anon.version import CRATE_VERSION, CRATE_VERSION_DATE

log = logging.getLogger(__name__)


# =============================================================================
# Home
# =============================================================================

def home(request: HttpRequest) -> HttpResponse:
    """
    The home (main menu) view.
    """
    # leaflets = [{'key': x[0], 'name': x[1]} for x in Leaflet.LEAFLET_CHOICES]
    # assert False
    # log.critical("IP Address for debug-toolbar: " + request.META['REMOTE_ADDR'])  # noqa
    # log.critical(f"MIDDLEWARE_CLASSES: {repr(MIDDLEWARE_CLASSES)}")
    context = {
        'nav_on_main_menu': True,
        'is_clinician': is_clinician(request.user),
        'is_developer': is_developer(request.user),
        'safety_catch_on': settings.SAFETY_CATCH_ON,
        'developer_email': settings.DEVELOPER_EMAIL,
        # 'leaflets': leaflets,
    }
    context.update(query_context(request))
    return render(request, 'home.html', context)


# =============================================================================
# About
# =============================================================================

def about(request: HttpRequest) -> HttpResponse:
    """
    The "about CRATE" view.
    """
    context = {
        'VERSION': CRATE_VERSION,
        'VERSION_DATE': CRATE_VERSION_DATE,
    }
    return render(request, 'about.html', context)
