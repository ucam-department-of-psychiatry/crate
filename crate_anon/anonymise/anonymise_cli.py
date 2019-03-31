#!/usr/bin/env python

"""
crate_anon/anonymise/anonymise_cli.py

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

**Command-line entry point for anonymisation.**

Split from the anonymisation functions so we can respond quickly to
command-line input; uses a delayed import when starting anonymisation.

"""

# Uses a delayed import (see below), so we can set up logging before
# using the config object.
import argparse
import logging
import os
from typing import List

from cardinal_pythonlib.argparse_func import RawDescriptionArgumentDefaultsHelpFormatter  # noqa
from cardinal_pythonlib.exceptions import die
from cardinal_pythonlib.extract_text import is_text_extractor_available
from cardinal_pythonlib.logs import configure_logger_for_colour

from crate_anon.anonymise.constants import (
    CONFIG_ENV_VAR,
    DEFAULT_CHUNKSIZE,
    DEFAULT_REPORT_EVERY,
    DEMO_CONFIG,
)
from crate_anon.version import CRATE_VERSION, CRATE_VERSION_DATE

log = logging.getLogger(__name__)

DEBUG_RUN_WITH_PDB = False

if DEBUG_RUN_WITH_PDB:
    from cardinal_pythonlib.debugging import pdb_run
else:
    pdb_run = None


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    """
    Command-line entry point. See command-line help.

    Calls :func:`crate_anon.anonymise.anonymise.anonymise`.
    """
    version = f"Version {CRATE_VERSION} ({CRATE_VERSION_DATE})"
    description = f"Database anonymiser. {version}. By Rudolf Cardinal."

    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "--version", action="version", version=version)
    parser.add_argument(
        "--democonfig", action="store_true",
        help="Print a demo config file")
    parser.add_argument(
        "--config",
        help=f"Config file (overriding environment variable {CONFIG_ENV_VAR})")
    parser.add_argument(
        '--verbose', '-v', action="store_true",
        help="Be verbose")
    parser.add_argument(
        '--reportevery', nargs="?", type=int, default=DEFAULT_REPORT_EVERY,
        help="Report insert progress every n rows in verbose mode")
    parser.add_argument(
        '--chunksize', nargs="?", type=int,
        default=DEFAULT_CHUNKSIZE,
        help="Number of records copied in a chunk when copying PKs from one "
             "database to another")
    parser.add_argument(
        "--process", nargs="?", type=int, default=0,
        help="For multiprocess mode: specify process number")
    parser.add_argument(
        "--nprocesses", nargs="?", type=int, default=1,
        help="For multiprocess mode: specify total number of processes "
             "(launched somehow, of which this is to be one)")
    parser.add_argument(
        "--processcluster", default="",
        help="Process cluster name")
    parser.add_argument(
        "--draftdd", action="store_true",
        help="Print a draft data dictionary")
    parser.add_argument(
        "--incrementaldd", action="store_true",
        help="Print an INCREMENTAL draft data dictionary")
    parser.add_argument(
        "--debugscrubbers", action="store_true",
        help="Report sensitive scrubbing information, for debugging")
    parser.add_argument(
        "--savescrubbers", action="store_true",
        help="Saves sensitive scrubbing information in admin database, "
             "for debugging")
    parser.add_argument(
        "--count", action="store_true",
        help="Count records in source/destination databases, then stop")
    parser.add_argument(
        "--dropremake", action="store_true",
        help="Drop/remake destination tables, then stop")
    parser.add_argument(
        "--optout", action="store_true",
        help="Build opt-out list, then stop")
    parser.add_argument(
        "--nonpatienttables", action="store_true",
        help="Process non-patient tables only")
    parser.add_argument(
        "--patienttables", action="store_true",
        help="Process patient tables only")
    parser.add_argument(
        "--index", action="store_true",
        help="Create indexes only")
    parser.add_argument(
        "--skip_dd_check", action="store_true",
        help="Skip data dictionary validity check")
    parser.add_argument(
        "--restrict",
        help="Restrict which patients are processed. Specify which field to "
             "base the restriction on or 'pid' for patient ids.")
    parser.add_argument(
        "--limits", nargs=2,
        help="Specify lower and upper limits of the field "
             "specified in '--restrict'")
    parser.add_argument(
        "--file",
        help="Specify a file with a list of values for the field "
             "specified in '--restrict'")
    parser.add_argument(
        "--list", nargs="+",
        help="Specify a list of values for the field "
             "specified in '--restrict'")
    parser.add_argument(
        "--filtertext", type=int,
        help="Filter out all free text over the specified length")

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "-i", "--incremental", dest="incremental", action="store_true",
        help="Process only new/changed information, where possible "
             "(* default)")
    mode_group.add_argument(
        "-f", "--full", dest="incremental", action="store_false",
        help="Drop and remake everything")
    parser.set_defaults(incremental=True)

    parser.add_argument(
        "--skipdelete", dest="skipdelete", action="store_true",
        help="For incremental updates, skip deletion of rows present in the "
             "destination but not the source")
    parser.add_argument(
        "--seed",
        help="String to use as the basis of the seed for the random number "
             "generator used for the transient integer RID (TRID). Leave "
             "blank to use the default seed (system time).")
    parser.add_argument(
        "--echo", action="store_true", help="Echo SQL")
    parser.add_argument(
        "--checkextractor", nargs='*',
        help="File extensions to check for availability of a text extractor "
             "(use a '.' prefix, and use the special extension 'None' to "
             "check the fallback processor")
    args = parser.parse_args()

    # -------------------------------------------------------------------------

    # Verbosity
    mynames = []  # type: List[str]
    if args.processcluster:
        mynames.append(args.processcluster)
    if args.nprocesses > 1:
        mynames.append(f"proc{args.process}")
    loglevel = logging.DEBUG if args.verbose else logging.INFO
    rootlogger = logging.getLogger()
    configure_logger_for_colour(rootlogger, loglevel, extranames=mynames)

    # Check text converters
    if args.checkextractor:
        for ext in args.checkextractor:
            if ext.lower() == 'none':
                ext = None
            available = is_text_extractor_available(ext)
            print(f"Text extractor for extension {ext} present: {available}")
        return

    if args.config:
        os.environ[CONFIG_ENV_VAR] = args.config

    # Demo config?
    if args.democonfig:
        print(DEMO_CONFIG)
        return

    # Delayed import; pass everything else on
    from crate_anon.anonymise.anonymise import anonymise  # delayed import
    try:
        anonymise(args)
    except Exception as exc:
        log.critical("TERMINAL ERROR FROM THIS PROCESS")  # so we see proc#
        die(exc)


# =============================================================================
# Command-line entry point
# =============================================================================

if __name__ == '__main__':
    if DEBUG_RUN_WITH_PDB:
        pdb_run(main)
    else:
        main()
