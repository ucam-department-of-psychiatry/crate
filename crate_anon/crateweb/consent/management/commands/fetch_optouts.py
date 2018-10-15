#!/usr/bin/env python

"""
crate_anon/crateweb/consent/management/commands/fetch_optouts.py

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

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import translation

from crate_anon.crateweb.consent.lookup import gen_opt_out_pids_mpids

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Fetch patient IDs (PIDs) and master patient IDs (MPIDs, e.g. NHS "
        "numbers) from the clinical consent-mode lookup database, and store "
        "them in a file (e.g. for use by the CRATE anonymiser)."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--pidfile", required=True,
            help="Filename to store PIDs in (one line per PID)")
        parser.add_argument(
            "--mpidfile", required=True,
            help="Filename to store MPIDs in (one line per PID)")

    def handle(self, *args, **options):
        opts = Namespace(**options)
        # Activate the current language, because it won't get activated later.
        try:
            translation.activate(settings.LANGUAGE_CODE)
        except AttributeError:
            pass
        # noinspection PyTypeChecker
        fetch_optouts(opts)


def fetch_optouts(opts: Namespace) -> None:
    pid_filename = opts.pidfile  # type: str
    mpid_filename = opts.mpidfile  # type: str
    log.info(
        "Fetching opt-outs from database to files. Storing PIDs to {!r}, "
        "MPIDs to {!r}.".format(pid_filename, mpid_filename))
    source_db = settings.CLINICAL_LOOKUP_CONSENT_DB
    with open(pid_filename, "w") as pf:
        with open(mpid_filename, "w") as mf:
            for pid, mpid in gen_opt_out_pids_mpids(source_db):
                if pid is not None and pid != "":
                    pf.write(str(pid) + "\n")
                if mpid is not None and mpid != "":
                    mf.write(str(mpid) + "\n")
    log.info("Done.")


def main():
    command = Command()
    parser = ArgumentParser()
    command.add_arguments(parser)
    cmdargs = parser.parse_args()
    fetch_optouts(cmdargs)


if __name__ == '__main__':
    main()
