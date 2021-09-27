#!/usr/bin/env python

"""
crate_anon/ancillary/timely_project/filter_cpft_rio_data_dictionary.py

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

**Helper code for a specific project. Not of general interest.**

For the MRC TIMELY project (Moore, grant MR/T046430/1), filter a CPFT RiO
data dictionary, cutting it down.

"""

import argparse
import logging

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger

from crate_anon.anonymise.config import Config
from crate_anon.anonymise.dd import DataDictionary
from crate_anon.anonymise.ddr import DataDictionaryRow

log = logging.getLogger(__name__)


# =============================================================================
# Deciding about rows
# =============================================================================

EXCLUDE_TABLES = [
    # ***
]
INCLUDE_TABLES = [
    "patient"
]

# And for convenience:
EXCLUDE_TABLES_LOWER = [x.lower() for x in EXCLUDE_TABLES]
INCLUDE_TABLES_LOWER = [x.lower() for x in INCLUDE_TABLES]


def keep(row: DataDictionaryRow) -> bool:
    """
    Filters each row. Returns ``True`` to keep, ``False`` to reject.
    """
    table_lower = row.src_table.lower()
    if table_lower in EXCLUDE_TABLES_LOWER:
        return False
    if table_lower in INCLUDE_TABLES_LOWER:
        return True
    # Default:
    return False


# =============================================================================
# File handling
# =============================================================================

def filter_dd(input_filename: str, output_filename: str) -> None:
    """
    Reads a data dictionary, filters it, and writes the output.
    """
    log.info(f"Reading data dictionary: {input_filename}")
    config = Config()  # read config file from environment variable
    dd = DataDictionary.create_from_file(input_filename, config)
    log.info("Filtering.")
    dd.remove_rows_by_filter(keep)
    log.info(f"Writing data dictionary: {output_filename}")
    dd.write_tsv_file(output_filename)


# =============================================================================
# Command-line handling
# =============================================================================

def main() -> None:
    """
    Command-line entry point.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "input", type=str,
        help="Data dictionary file to read"
    )
    parser.add_argument(
        "output", type=str,
        help="Data dictionary file to write"
    )
    args = parser.parse_args()

    main_only_quicksetup_rootlogger()
    filter_dd(input_filename=args.input, output_filename=args.output)


if __name__ == "__main__":
    main()
