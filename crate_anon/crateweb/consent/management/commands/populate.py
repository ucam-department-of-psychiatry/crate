#!/usr/bin/env python3
# crate_anon/crateweb/consent/management/commands/populate.py

from django.core.management.base import BaseCommand
from crate_anon.crateweb.consent.models import Leaflet


class Command(BaseCommand):
    help = "Populate the database with leaflet entries if necessary"

    def handle(self, *args, **options):
        Leaflet.populate()
        self.stdout.write("Successfully populated leaflets")
