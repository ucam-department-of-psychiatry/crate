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

For first cut:

- no free text
- include things USEFUL FOR ANONYMISATION, e.g. client_name_history, but they
  will not in the final output.
- include things of (final) interest (obviously).

"""

import argparse
import logging
import re
from typing import List

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from sqlalchemy.dialects.mssql.base import dialect as sql_server_dialect

from crate_anon.anonymise.config import Config
from crate_anon.anonymise.dd import DataDictionary
from crate_anon.anonymise.ddr import DataDictionaryRow

log = logging.getLogger(__name__)


# =============================================================================
# Deciding about rows
# =============================================================================

EXCLUDE_TABLE_REGEXES = [
    "user.*",  # Custom forms added by CPFT; usually semi-structured/free text (but sometimes more useful)  # noqa
    "cpft_core_assessment_v2_kcsa_children_in_household",  #  about people other than the patient  # noqa
]
INCLUDE_TABLE_REGEXES = [
    "assessmentdates",
    "care_plan_.*",
    "careplanproblemorder",
    "client.*",  # client* and client_*
    "deceased",
    "dgndiagnosissecondary",  # dgn = diagnosis
    "diagnosis",
    "ims.*",  # e.g. ward attendance
    "inpatient_.*",  # admissions etc.
    "mntclient.*",  # mnt = Mental Health Act
    "referral.*",
    "rio_manual_opt_out",
    "snomed_client",
]

EXCLUDE_TABLES_RE_COMPILED = [re.compile(x) for x in EXCLUDE_TABLE_REGEXES]
INCLUDE_TABLES_RE_COMPILED = [re.compile(x) for x in INCLUDE_TABLE_REGEXES]


# Nasty:
reported = set()


def report(text: str) -> None:
    """
    Reports a decision, but only once.
    """
    global reported
    if text in reported:
        return
    log.debug(text)
    reported.add(text)


def keep(row: DataDictionaryRow, system_tables: List[str]) -> bool:
    """
    Filters each row. Returns ``True`` to keep, ``False`` to reject.
    """
    table_lower = row.src_table.lower()

    for r in EXCLUDE_TABLES_RE_COMPILED:
        if r.match(table_lower):
            report(f"Excluding specifically: {table_lower}")
            return False

    for r in INCLUDE_TABLES_RE_COMPILED:
        if r.match(table_lower):
            report(f"INCLUDING specifically: {table_lower}")
            return True

    if table_lower in system_tables:
        report(f"INCLUDING system table: {table_lower}")
        return True

    # Default:
    report(f"Excluding by default: {table_lower}")
    return False


# =============================================================================
# File handling
# =============================================================================

def filter_dd(input_filename: str, output_filename: str) -> None:
    """
    Reads a data dictionary, filters it, and writes the output.
    """
    log.info(f"Reading data dictionary: {input_filename}")
    # We don't care about the actual config, so we use a mock one:
    config = Config(mock=True, open_databases=False)
    dd = DataDictionary.create_from_file(
        input_filename,
        config,
        check_valid=False,
        override_dialect=sql_server_dialect
    )
    system_tables = [
        table.lower()
        for table in dd.get_tables_w_no_pt_info()
    ]
    # log.critical(f"system_tables: {system_tables}")

    def keep_row(row: DataDictionaryRow) -> bool:
        return keep(row, system_tables)

    log.info(f"Filtering. Starting with {dd.n_rows} rows...")
    dd.remove_rows_by_filter(keep_row)
    log.info(f"... ending with {dd.n_rows} rows.")
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
    parser.add_argument(
        "--nocolour", action="store_true",
        help="Disable colour in logs"
    )
    args = parser.parse_args()

    if args.nocolour:
        logging.basicConfig(level=logging.DEBUG)
    else:
        main_only_quicksetup_rootlogger()
    filter_dd(input_filename=args.input, output_filename=args.output)


if __name__ == "__main__":
    main()
