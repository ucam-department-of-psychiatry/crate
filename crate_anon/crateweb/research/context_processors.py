#!/usr/bin/env python
# crate_anon/crateweb/research/context_processors.py

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
