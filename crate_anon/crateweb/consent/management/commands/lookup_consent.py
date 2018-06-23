#!/usr/bin/env python
# crate_anon/crateweb/core/management/commands/lookup_consent.py

"""
===============================================================================

    Copyright (C) 2015-2018 Rudolf Cardinal (rudolf@pobox.com).

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
"""

from argparse import ArgumentParser, Namespace
import logging
from typing import List

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import translation

from crate_anon.crateweb.consent.lookup import lookup_consent

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Tests lookup of the consent mode from the relevant CLINICAL database."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--nhs_numbers", required=True, type=int, nargs="+",
            help="NHS numbers to look up")

    def handle(self, *args, **options):
        opts = Namespace(**options)
        # Activate the current language, because it won't get activated later.
        try:
            translation.activate(settings.LANGUAGE_CODE)
        except AttributeError:
            pass
        # noinspection PyTypeChecker
        cli_lookup_consent(opts)


def cli_lookup_consent(opts: Namespace) -> None:
    nhs_numbers = opts.nhs_numbers  # type: List[int]
    source_db = settings.CLINICAL_LOOKUP_CONSENT_DB
    log.info("Testing consent lookup from clinical database: {}.".format(
        source_db))
    for nhs_num in nhs_numbers:
        decisions = []  # type: List[str]
        consent_mode = lookup_consent(
            nhs_number=nhs_num,
            source_db=source_db,
            decisions=decisions
        )
        log.info("NHS number: {}. Consent mode: {}".format(
            nhs_num, consent_mode))
        log.debug("Decisions: {}".format(" // ".join(decisions)))
    log.info("Done.")


def main():
    command = Command()
    parser = ArgumentParser()
    command.add_arguments(parser)
    cmdargs = parser.parse_args()
    cli_lookup_consent(cmdargs)


if __name__ == '__main__':
    main()
