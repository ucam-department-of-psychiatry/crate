#!/usr/bin/env python
# crate_anon/anonymise/anonymise_cli.py

# Uses a delayed import (see below), so we can set up logging before
# using the config object.
import argparse
import logging
import os

from cardinal_pythonlib.rnc_extract_text import is_text_extractor_available

from crate_anon.anonymise.constants import (
    CONFIG_ENV_VAR,
    DEFAULT_CHUNKSIZE,
    DEFAULT_REPORT_EVERY,
    DEMO_CONFIG,
)
from crate_anon.common.debugfunc import pdb_run
from crate_anon.common.logsupport import configure_logger_for_colour
from crate_anon.version import VERSION, VERSION_DATE


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    """
    Command-line entry point.
    """
    version = "Version {} ({})".format(VERSION, VERSION_DATE)
    description = "Database anonymiser. {version}. By Rudolf Cardinal.".format(
        version=version,
    )

    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=version)
    parser.add_argument("--democonfig", action="store_true",
                        help="Print a demo config file")
    parser.add_argument("--config",
                        help="Config file (overriding environment "
                             "variable {})".format(CONFIG_ENV_VAR))
    parser.add_argument('--verbose', '-v', action="store_true",
                        help="Be verbose")
    parser.add_argument('--reportevery', nargs="?", type=int,
                        default=DEFAULT_REPORT_EVERY,
                        help="Report insert progress every n rows in verbose "
                             "mode (default {})".format(DEFAULT_REPORT_EVERY))
    parser.add_argument('--chunksize', nargs="?", type=int,
                        default=DEFAULT_CHUNKSIZE,
                        help="Number of records copied in a chunk when copying"
                             " PKs from one database to another"
                             " (default {})".format(DEFAULT_CHUNKSIZE))
    parser.add_argument("--process", nargs="?", type=int, default=0,
                        help="For multiprocess mode: specify process number")
    parser.add_argument("--nprocesses", nargs="?", type=int, default=1,
                        help="For multiprocess mode: specify "
                             "total number of processes (launched somehow, of "
                             "which this is to be one)")
    parser.add_argument("--processcluster", default="",
                        help="Process cluster name")
    parser.add_argument("--draftdd", action="store_true",
                        help="Print a draft data dictionary")
    parser.add_argument("--incrementaldd", action="store_true",
                        help="Print an INCREMENTAL draft data dictionary")
    parser.add_argument("--debugscrubbers", action="store_true",
                        help="Report sensitive scrubbing information, for "
                             "debugging")
    parser.add_argument("--savescrubbers", action="store_true",
                        help="Saves sensitive scrubbing information in admin "
                             "database, for debugging")
    parser.add_argument("--count", action="store_true",
                        help="Count records in source/destination databases, "
                             "then stop")
    parser.add_argument("--dropremake", action="store_true",
                        help="Drop/remake destination tables, then stop")
    parser.add_argument("--optout", action="store_true",
                        help="Build opt-out list, then stop")
    parser.add_argument("--nonpatienttables", action="store_true",
                        help="Process non-patient tables only")
    parser.add_argument("--patienttables", action="store_true",
                        help="Process patient tables only")
    parser.add_argument("--index", action="store_true",
                        help="Create indexes only")

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
    parser.add_argument("--echo", action="store_true", help="Echo SQL")
    parser.add_argument(
        "--checkextractor", nargs='*',
        help="File extensions to check for availability of a text extractor "
             "(use a '.' prefix, and use the special extension 'None' to "
             "check the fallback processor")
    args = parser.parse_args()

    # -------------------------------------------------------------------------

    # Verbosity
    mynames = []
    if args.processcluster:
        mynames.append(args.processcluster)
    if args.nprocesses > 1:
        mynames.append("proc{}".format(args.process))
    loglevel = logging.DEBUG if args.verbose else logging.INFO
    rootlogger = logging.getLogger()
    configure_logger_for_colour(rootlogger, loglevel, extranames=mynames)

    # Check text converters
    if args.checkextractor:
        for ext in args.checkextractor:
            if ext.lower() == 'none':
                ext = None
            available = is_text_extractor_available(ext)
            print("Text extractor for extension {} present: {}".format(
                ext, available))
        return
    
    if args.config:
        os.environ[CONFIG_ENV_VAR] = args.config

    # Demo config?
    if args.democonfig:
        print(DEMO_CONFIG)
        return

    # Delayed import; pass everything else on
    from crate_anon.anonymise.anonymise import anonymise  # delayed import
    anonymise(args)


# =============================================================================
# Command-line entry point
# =============================================================================

if __name__ == '__main__':
    pdb_run(main)
