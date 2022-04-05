#!/usr/bin/env python

"""
crate_anon/crateweb/core/management/commands/ensuresuperuser.py

===============================================================================

    Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).

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
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

===============================================================================
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    # Like the 'createsuperuser' command but:
    # * Non-interactive
    # * Uses environment variables not arguments
    # * Doesn't raise an exception if the user already exists
    #
    # Unfortunately the 'createsuperuser' command isn't written in a way that
    # makes it easily extendable

    help = (
        "Creates an admin user in the default database if it doesn't "
        "already exist"
    )

    def handle(self, *args, **options):
        User = get_user_model()

        # We just support the default names for a user's attributes for now
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        if username is None:
            raise CommandError("You must set DJANGO_SUPERUSER_USERNAME")

        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        if password is None:
            raise CommandError("You must set DJANGO_SUPERUSER_PASSWORD")

        email = os.environ.get("DJANGO_SUPERUSER_EMAIL") or ""

        user, created = User.objects.get_or_create(username=username)
        user.is_superuser = True
        user.is_staff = True
        user.set_password(password)
        user.email = email
        user.save()

        if options["verbosity"] >= 1:
            if created:
                self.stdout.write("Superuser created successfully.")
            else:
                self.stdout.write("Superuser updated successfully.")
