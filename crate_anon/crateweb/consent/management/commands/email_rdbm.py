#!/usr/bin/env python

"""
crate_anon/crateweb/consent/management/commands/email_rdbm.py

===============================================================================

    Copyright (C) 2015-2020 Rudolf Cardinal (rudolf@pobox.com).

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

**Django management command to e-mail the RDBM.**

"""

import logging
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser

from crate_anon.crateweb.consent.tasks import email_rdbm_task
log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Django management command to e-mail the RDBM.
    """
    help = "Email the RDBM"

    def add_arguments(self, parser: CommandParser) -> None:
        # docstring in superclass
        parser.add_argument(
            "--subject", type=str,
            help="Subject")
        parser.add_argument(
            "--text", type=str,
            help="Text body")
        parser.add_argument(
            "--queue", action="store_true",
            help="E-mail via backend task queue (rather than immediately)")

    def handle(self, *args: str, **options: Any) -> None:
        # docstring in superclass
        subject = options['subject'] or ""
        text = options['text'] or ""
        queue = options['queue']
        if not subject and not text:
            log.error("Neither text nor subject specified; "
                      "ignoring request to e-mail RDBM")
            return
        log.info(f"RDBM is: {settings.RDBM_EMAIL}")
        if queue:
            log.info("Placing request to e-mail RDBM into backend task queue")
            email_rdbm_task.delay(subject=subject, text=text)
        else:
            log.info("E-mailing RDBM now")
            email_rdbm_task(subject=subject, text=text)
