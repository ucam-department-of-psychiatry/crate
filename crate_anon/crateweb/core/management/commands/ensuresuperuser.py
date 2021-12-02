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

    help = ("Creates an admin user in the default database if it doesn't "
            "already exist")

    def handle(self, *args, **options):
        User = get_user_model()

        # We just support the default names for a user's attributes for now
        user_data = {"is_staff": True, "is_superuser": True}

        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        if username is None:
            raise CommandError("You must set DJANGO_SUPERUSER_USERNAME")
        user_data["username"] = username

        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        if password is None:
            raise CommandError("You must set DJANGO_SUPERUSER_PASSWORD")
        user_data["password"] = password

        email = os.environ.get("DJANGO_SUPERUSER_EMAIL") or ""
        user_data["email"] = email

        User.objects.update_or_create(**user_data)
