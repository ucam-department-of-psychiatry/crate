#!/usr/bin/env python3
# core/views.py

from django.shortcuts import render
# from consent.models import Leaflet
from core.utils import is_developer


# =============================================================================
# Home
# =============================================================================

def home(request):
    # leaflets = [{'key': x[0], 'name': x[1]} for x in Leaflet.LEAFLET_CHOICES]
    # assert False
    return render(request, 'home.html', {
        'nav_on_main_menu': True,
        'is_developer': is_developer(request.user),
        # 'leaflets': leaflets,
    })
