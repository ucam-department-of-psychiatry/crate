#!/usr/bin/env python

"""
crate_anon/crateweb/consent/management/commands/fetch_optouts.py

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

**Django management command to fetch PIDs/MPIDs from the consent-mode
database for patients who wish to opt out entirely, and store them in a file
(e.g. for the CRATE anonymiser).**

"""

from argparse import ArgumentParser, Namespace
import logging
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import translation

from crate_anon.crateweb.consent.lookup import gen_opt_out_pids_mpids

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Django management command to fetch PIDs/MPIDs for opt-out patients from the
    clinical consent-mode lookup database, and store them in a file (e.g. for
    use by the CRATE anonymiser).
    """
    help = (
        "Fetch patient IDs (PIDs) and master patient IDs (MPIDs, e.g. NHS "
        "numbers) from the clinical consent-mode lookup database, and store "
        "them in a file (e.g. for use by the CRATE anonymiser)."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        # docstring in superclass
        parser.add_argument(
            "--pidfile", required=True,
            help="Filename to store PIDs in (one line per PID)")
        parser.add_argument(
            "--mpidfile", required=True,
            help="Filename to store MPIDs in (one line per PID)")

    def handle(self, *args: str, **options: Any) -> None:
        # docstring in superclass
        opts = Namespace(**options)
        # Activate the current language, because it won't get activated later.
        try:
            translation.activate(settings.LANGUAGE_CODE)
        except AttributeError:
            pass
        # noinspection PyTypeChecker
        fetch_optouts(
            pid_filename=opts.pid_filename,
            mpid_filename=opts.mpid_filename,
        )


def fetch_optouts(pid_filename: str, mpid_filename: str) -> None:
    """
    Fetch opt-out PIDs/MPIDs from the clinical consent-mode lookup database
    (defined via Django ``settings.CLINICAL_LOOKUP_CONSENT_DB``) and write them
    to files.

    Args:
        pid_filename: name of the filename to receive PIDs
        mpid_filename: name of the filename to receive MPIDs
    """
    log.info(
        f"Fetching opt-outs from database to files. Storing PIDs to "
        f"{pid_filename!r}, MPIDs to {mpid_filename!r}.")
    source_db = settings.CLINICAL_LOOKUP_CONSENT_DB
    with open(pid_filename, "w") as pf:
        with open(mpid_filename, "w") as mf:
            for pid, mpid in gen_opt_out_pids_mpids(source_db):
                if pid is not None and pid != "":
                    pf.write(str(pid) + "\n")
                if mpid is not None and mpid != "":
                    mf.write(str(mpid) + "\n")
    log.info("Done.")


def main() -> None:
    """
    Command-line entry point (not typically used directly).
    """
    command = Command()
    parser = ArgumentParser()
    command.add_arguments(parser)
    cmdargs = parser.parse_args()
    fetch_optouts(
        pid_filename=cmdargs.pid_filename,
        mpid_filename=cmdargs.mpid_filename,
    )


if __name__ == '__main__':
    main()
