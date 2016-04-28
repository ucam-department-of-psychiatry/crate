#!/usr/bin/env python
# crate_anon/anonymise/anonymise_main.py

# Uses a delayed import (see below), so we can set up logging before
# using the config object.
import argparse
import logging
import os
import sys

from crate_anon.anonymise.constants import (
    COLOUR_HANDLER,
    LOG_DATEFMT,
    LOG_FORMAT,
)
from crate_anon.version import VERSION, VERSION_DATE


# =============================================================================
# Helper functions
# =============================================================================

def configure_logger_for_colour(log, remove_existing=True):
    """
    Applies a preconfigured datetime/colour scheme to a logger.
    Should ONLY be called from the "if __name__ == 'main'" script:
        https://docs.python.org/3.4/howto/logging.html#library-config
    """
    if remove_existing:
        log.handlers = []  # http://stackoverflow.com/questions/7484454
    log.addHandler(COLOUR_HANDLER)


# =============================================================================
# Main
# =============================================================================

def main():
    """
    Command-line entry point.
    """
    version = "Version {} ({})".format(VERSION, VERSION_DATE)
    description = """
Database anonymiser. {version}. By Rudolf Cardinal.

Sample usage:
    {prog} -c > testconfig.ini  # generate sample config file
    {prog} -d testconfig.ini > testdd.tsv  # generate draft data dict.
    {prog} testconfig.ini  # run""".format(
        prog=os.path.basename(sys.argv[0]),
        version=version,
    )

    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-n", "--version", action="version", version=version)
    parser.add_argument('--verbose', '-v', action='count', default=0,
                        help="Be verbose (use twice for extra verbosity)")
    parser.add_argument('-r', '--report', nargs="?", type=int, default=1000,
                        help="Report insert progress every n rows in verbose "
                             "mode (default 1000)")
    parser.add_argument("--process", nargs="?", type=int, default=0,
                        help="For multiprocess patient-table mode: specify "
                             "process number")
    parser.add_argument("--nprocesses", nargs="?", type=int, default=1,
                        help="For multiprocess patient-table mode: specify "
                             "total number of processes (launched somehow, of "
                             "which this is to be one)")
    parser.add_argument("--processcluster", default="",
                        help="Process cluster name")
    parser.add_argument("--draftdd", action="store_true",
                        help="Print a draft data dictionary")
    parser.add_argument("--incrementaldd", action="store_true",
                        help="Print an INCREMENTAL draft data dictionary")
    parser.add_argument("--makeddpermitbydefaultdangerous",
                        action="store_true",
                        help="When creating or adding to a data dictionary, "
                             "set the 'omit' flag to False. DANGEROUS.")
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
    parser.add_argument("--nonpatienttables", action="store_true",
                        help="Process non-patient tables only")
    parser.add_argument("--patienttables", action="store_true",
                        help="Process patient tables only")
    parser.add_argument("--index", action="store_true",
                        help="Create indexes only")
    parser.add_argument("-i", "--incremental",
                        dest="incremental", action="store_true",
                        help="Process only new/changed information, where "
                             "possible")
    parser.add_argument("-f", "--full",
                        dest="incremental", action="store_false",
                        help="Process only new/changed information, where "
                             "possible")
    parser.set_defaults(incremental=True)
    parser.add_argument("--seed",
                        help="String to use as the basis of the seed for the "
                             "random number generator used for the transient "
                             "integer RID (TRID). Leave blank to use the "
                             "default seed (system time).")
    parser.add_argument("--echo", action="store_true",
                        help="Echo SQL")
    args = parser.parse_args()

    # -------------------------------------------------------------------------

    # Verbosity
    mynames = []
    if args.processcluster:
        mynames.append(args.processcluster)
    if args.nprocesses > 1:
        mynames.append("process {}".format(args.process))
    loglevel = logging.DEBUG if args.verbose >= 1 else logging.INFO
    logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATEFMT,
                        level=loglevel)
    rootlogger = logging.getLogger()
    rootlogger.setLevel(loglevel)
    configure_logger_for_colour(rootlogger)  # configure root logger

    # rnc_log.reset_logformat_timestamped(
    #     rootlogger,
    #     extraname=" ".join(mynames),
    #     level=mainloglevel
    # )

    # Delayed import; pass everything else on
    from crate_anon.anonymise.anonymise import anonymise  # delayed import
    anonymise(args)


# =============================================================================
# Command-line entry point
# =============================================================================

if __name__ == '__main__':
    main()
