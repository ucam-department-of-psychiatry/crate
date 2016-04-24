#!/usr/bin/env python3
# core/views.py

import logging
from django.shortcuts import render
from crate_anon.crateweb.core.utils import is_developer

log = logging.getLogger(__name__)


# =============================================================================
# Home
# =============================================================================

def home(request):
    # leaflets = [{'key': x[0], 'name': x[1]} for x in Leaflet.LEAFLET_CHOICES]
    # assert False
    # log.critical("IP Address for debug-toolbar: " + request.META['REMOTE_ADDR'])  # noqa
    # log.critical("MIDDLEWARE_CLASSES: {}".format(repr(MIDDLEWARE_CLASSES)))
    return render(request, 'home.html', {
        'nav_on_main_menu': True,
        'is_developer': is_developer(request.user),
        # 'leaflets': leaflets,
    })
