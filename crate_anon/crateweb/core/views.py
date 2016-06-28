#!/usr/bin/env python3
# core/views.py

import logging
from django.conf import settings
from django.shortcuts import render
from crate_anon.crateweb.core.utils import is_developer
from crate_anon.crateweb.research.views import query_context

log = logging.getLogger(__name__)


# =============================================================================
# Home
# =============================================================================

def home(request):
    # leaflets = [{'key': x[0], 'name': x[1]} for x in Leaflet.LEAFLET_CHOICES]
    # assert False
    # log.critical("IP Address for debug-toolbar: " + request.META['REMOTE_ADDR'])  # noqa
    # log.critical("MIDDLEWARE_CLASSES: {}".format(repr(MIDDLEWARE_CLASSES)))
    context = {
        'nav_on_main_menu': True,
        'is_developer': is_developer(request.user),
        'safety_catch_on': settings.SAFETY_CATCH_ON,
        'developer_email': settings.DEVELOPER_EMAIL,
        # 'leaflets': leaflets,
    }
    context.update(query_context(request))
    return render(request, 'home.html', context)
