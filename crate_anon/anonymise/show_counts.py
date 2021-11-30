#!/usr/bin/env python

"""
crate_anon/anonymise/show_counts.py

===============================================================================

    Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).

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
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

===============================================================================

**Show record counts from source/destination database.**

"""

import argparse
import logging
import os
from typing import List, Tuple

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from cardinal_pythonlib.sqlalchemy.core_query import count_star

from crate_anon.anonymise.config import Config
from crate_anon.anonymise.constants import ANON_CONFIG_ENV_VAR
from crate_anon.common.formatting import print_record_counts
from crate_anon.version import CRATE_VERSION_PRETTY

log = logging.getLogger(__name__)


# =============================================================================
# Show counts
# =============================================================================

def show_source_counts(config: Config) -> None:
    """
    Show (print to stdout) the number of records in all source tables.
    """
    print("SOURCE TABLE RECORD COUNTS:")
    counts = []  # type: List[Tuple[str, int]]
    for d in config.dd.get_source_databases():
        session = config.sources[d].session
        for t in config.dd.get_src_tables(d):
            n = count_star(session, t)
            counts.append((f"{d}.{t}", n))
    print_record_counts(counts)


def show_dest_counts(config: Config) -> None:
    """
    Show (print to stout) the number of records in all destination tables.
    """
    print("DESTINATION TABLE RECORD COUNTS:")
    counts = []  # type: List[Tuple[str, int]]
    session = config.destdb.session
    for t in config.dd.get_dest_tables():
        n = count_star(session, t)
        counts.append((f"DESTINATION: {t}", n))
    print_record_counts(counts)


def show_record_counts(config: Config) -> None:
    """
    Show record counts for source/destination databases.
    """
    # Load/validate config
    config.load_dd()
    config.check_valid()

    show_source_counts(config)
    show_dest_counts(config)


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    """
    Command-line entry point.
    """
    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(
        description=f"Print record counts from source/destination databases. "
                    f"({CRATE_VERSION_PRETTY})",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument(
        "--config",
        help=f"Config file (overriding environment variable "
             f"{ANON_CONFIG_ENV_VAR}).")
    parser.add_argument(
        '--verbose', '-v', action="store_true",
        help="Be verbose")

    args = parser.parse_args()

    # -------------------------------------------------------------------------
    # Verbosity, logging
    # -------------------------------------------------------------------------

    loglevel = logging.DEBUG if args.verbose else logging.INFO
    main_only_quicksetup_rootlogger(level=loglevel)

    # -------------------------------------------------------------------------
    # Onwards
    # -------------------------------------------------------------------------

    if args.config:
        os.environ[ANON_CONFIG_ENV_VAR] = args.config
    from crate_anon.anonymise.config_singleton import config  # delayed import
    show_record_counts(config)
