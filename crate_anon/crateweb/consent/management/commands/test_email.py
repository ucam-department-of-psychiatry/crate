#!/usr/bin/env python3
# crate_anon/crateweb/consent/management/commands/test_email.py

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Test email to RDBM (without saving to database)"

    def handle(self, *args, **options):
        sender = settings.EMAIL_SENDER
        recipient = settings.DEVELOPER_EMAIL
        send_mail(
            'CRATE test e-mail',
            'Message body',
            sender,
            [recipient],
            fail_silently=False,
        )
        self.stdout.write("Successfully sent e-mail from {} to {}".format(
            sender, recipient))
