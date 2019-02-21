#!/usr/bin/env python

"""
crate_anon/crateweb/core/context_processors.py

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

**A common context dictionary for all Django requests.**

"""

from typing import Any, Dict

from django.conf import settings
from django.http.request import HttpRequest

from crate_anon.common.constants import CRATE_DOCS_URL


# noinspection PyUnusedLocal
def common_context(request: HttpRequest) -> Dict[str, Any]:
    """
    Returns a context used across the site.

    Args:
        request: the :class:`django.http.request.HttpRequest`

    Returns:
        dict: a context dictionary

    """
    return {
        'CRATE_DOCS_URL': CRATE_DOCS_URL,
        'nav_on_main_menu': False,
        'RESEARCH_DB_TITLE': settings.RESEARCH_DB_TITLE,
    }
    # Try to minimize SQL here, as these calls will be used for EVERY
    # request.
    # This problem can partially be circumvented with a per-request cache; see
    # http://stackoverflow.com/questions/3151469/per-request-cache-in-django
    # But good practice is: keep queries to a minimum.
