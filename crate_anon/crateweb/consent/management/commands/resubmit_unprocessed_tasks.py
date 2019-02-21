#!/usr/bin/env python

"""
crate_anon/crateweb/consent/management/commands/resubmit_unprocessed_tasks.py

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

**Django management command to resubmit unprocessed tasks.**

"""

import logging
from typing import Any

from django.core.management.base import BaseCommand

from crate_anon.crateweb.consent.tasks import resubmit_unprocessed_tasks_task

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Django management command to resubmit unprocessed tasks (in case Celery
    jobs have been lost).
    """
    help = "Resubmit unprocessed tasks (in case Celery jobs have been lost)"

    def handle(self, *args: str, **options: Any) -> None:
        # docstring in superclass
        resubmit_unprocessed_tasks_task.delay()
        log.info("Initial Celery task submitted; this will trigger "
                 "more tasks for any unprocessed work.")
