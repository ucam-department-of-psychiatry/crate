#!/usr/bin/env python
# crate_anon/crateweb/research/context_processors.py

"""
===============================================================================
    Copyright (C) 2015-2018 Rudolf Cardinal (rudolf@pobox.com).

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
"""

from typing import Any, Dict

from django.conf import settings
from django.http.request import HttpRequest
# from crate_anon.crateweb.research.models import Query
# from crate_anon.crateweb.extra.request_cache import get_request_cache


# noinspection PyUnusedLocal
def common_context(request: HttpRequest) -> Dict[str, Any]:
    return {
        'RESEARCH_DB_TITLE': settings.RESEARCH_DB_TITLE,
        'nav_on_main_menu': False,
    }
    # Try to minimize SQL here, as these calls will be used for EVERY
    # request.
    # This problem can partially be circumvented with a per-request cache; see
    # http://stackoverflow.com/questions/3151469/per-request-cache-in-django
    # But good practice is: keep queries to a minimum.
