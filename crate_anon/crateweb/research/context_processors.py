#!/usr/bin/env python3
# research/context_processors.py

from django.conf import settings
from crate_anon.crateweb.research.models import Query


def common_context(request):
    query_id = Query.get_active_query_id_or_none(request)
    return {
        'RESEARCH_DB_TITLE': settings.RESEARCH_DB_TITLE,
        'nav_on_main_menu': False,
        'query_selected': query_id is not None,
        'current_query_id': query_id,
    }
    # Try to minimize SQL here, as these calls will be used for EVERY
    # request.
