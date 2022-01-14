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

        if options['verbosity'] >= 1:
            if created:
                self.stdout.write("Superuser created successfully.")
            else:
                self.stdout.write("Superuser updated successfully.")
