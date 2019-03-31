#!/usr/bin/env python

"""
crate_anon/crateweb/consent/management/commands/lookup_patient.py

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

**Django management command to test patient lookup from the clinical
database.**

"""

from argparse import ArgumentParser, Namespace
import logging
import pdb
import sys
import traceback
from typing import Any, List

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import translation

from crate_anon.crateweb.consent.lookup import lookup_patient

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Django management command to test patient lookup from the clinical
    database.
    """
    help = (
        "Tests lookup of patient details from the relevant CLINICAL database."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        # docstring in superclass
        parser.add_argument(
            "--nhs_numbers", required=True, type=int, nargs="+",
            help="NHS numbers to look up")

    def handle(self, *args: str, **options: Any) -> None:
        # docstring in superclass
        opts = Namespace(**options)
        # Activate the current language, because it won't get activated later.
        try:
            translation.activate(settings.LANGUAGE_CODE)
        except AttributeError:
            pass
        # noinspection PyBroadException,PyPep8
        try:
            # noinspection PyTypeChecker
            cli_lookup_patient(opts.nhs_numbers)
        except:
            type_, value, tb = sys.exc_info()
            traceback.print_exc()
            pdb.post_mortem(tb)


def cli_lookup_patient(nhs_numbers: List[int]) -> None:
    """
    Look up patient details for all specified NHS numbers, and display them to
    the Python log.

    Args:
        nhs_numbers: list of NHS numbers (as integers)
    """
    source_db = settings.CLINICAL_LOOKUP_DB
    log.info(f"Testing patient lookup from clinical database: {source_db}.")
    for nhs_num in nhs_numbers:
        patient_info = lookup_patient(
            nhs_number=nhs_num,
            source_db=source_db,
            save=False,
            existing_ok=False
        )
        log.info(f"NHS number: {nhs_num}. Patient info: {patient_info}")
    log.info("Done.")


def main():
    """
    Command-line entry point (not typically used directly).
    """
    command = Command()
    parser = ArgumentParser()
    command.add_arguments(parser)
    cmdargs = parser.parse_args()
    cli_lookup_patient(cmdargs.nhs_numbers)


if __name__ == '__main__':
    main()
