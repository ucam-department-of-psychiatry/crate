#!/usr/bin/env python

"""
crate_anon/anonymise/summarize_dd.py

===============================================================================

    Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

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

**Summarize an anonymisation data dictionary.**

"""

import argparse
from dataclasses import astuple, fields
import logging
import os

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from rich_argparse import ArgumentDefaultsRichHelpFormatter

from crate_anon.anonymise.config import Config
from crate_anon.anonymise.constants import ANON_CONFIG_ENV_VAR
from crate_anon.anonymise.dd import DDTableSummary
from crate_anon.common.spreadsheet import write_spreadsheet
from crate_anon.version import CRATE_VERSION_PRETTY

log = logging.getLogger(__name__)


# =============================================================================
# Summarize a data dictionary
# =============================================================================


def summarize_dd(config: Config, output_filename: str) -> None:
    """
    Produces a summary report about a data dictionary.

    Args:
        config:
            Anonymisation config object.
        output_filename:
            File for output ('-' for stdout).
    """
    config.load_dd(check_against_source_db=False)
    dd = config.dd
    header_row = tuple(f.name for f in fields(DDTableSummary))
    rows = [header_row] + [
        astuple(x) for x in dd.get_summary_info_all_tables()
    ]
    data = {"data_dictionary_report": rows}
    write_spreadsheet(output_filename, data)


# =============================================================================
# Main
# =============================================================================


def main() -> None:
    """
    Command-line entry point.
    """
    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(
        description=f"Draft a data dictionary for the anonymiser. "
        f"({CRATE_VERSION_PRETTY})",
        formatter_class=ArgumentDefaultsRichHelpFormatter,
    )

    parser.add_argument(
        "--config",
        help=f"Config file (overriding environment variable "
        f"{ANON_CONFIG_ENV_VAR}).",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Be verbose"
    )
    parser.add_argument(
        "--output", default="-", help="File for output; use '-' for stdout."
    )

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

    summarize_dd(config, args.output)
