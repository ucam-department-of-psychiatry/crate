#!/usr/bin/env python

"""
crate_anon/crateweb/consent/management/commands/test_email.py

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

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
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.

===============================================================================

**Django management command to test sending an e-mail.**

"""

from typing import Any

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """
    Django management command to test sending an e-mail to the RDBM (without
    saving it to the database).
    """
    help = "Test email to RDBM (without saving to database)"

    def handle(self, *args: str, **options: Any) -> None:
        # docstring in superclass
        sender = settings.EMAIL_SENDER
        recipient = settings.DEVELOPER_EMAIL
        send_mail(
            'CRATE test e-mail',
            'Message body',
            sender,
            [recipient],
            fail_silently=False,
        )
        self.stdout.write(
            f"Successfully sent e-mail from {sender} to {recipient}")
