#!/usr/bin/env python

"""
crate_anon/ancillary/timely_project/filter_data_dictionary.py

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

For the MRC TIMELY project (Moore, grant MR/T046430/1), filter a CRATE CPFT RiO
data dictionary, cutting it down.

Operates in 6 stages, following the approvals process.

The input and output are CRATE data dictionaries. Therefore, we want to include
tables required for anonymisation (e.g. names, NHS numbers) -- this may look
alarming, but isn't -- the subsequent anonymisation process will not yield that
information in the resulting de-identified database. We double-check that by
explicitly setting the "omit" flag to True for all such tables.

"""

import argparse
import copy
import logging
from typing import Dict, List, Optional, Type

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from sqlalchemy.dialects.mssql.base import dialect as mssql_server_dialect

from crate_anon.ancillary.timely_project.dd_criteria import (
    FieldCriterion,
    TableCriterion,
)
from crate_anon.ancillary.timely_project.timely_filter import (
    N_STAGES,
    TimelyDDFilter,
)
from crate_anon.ancillary.timely_project.timely_filter_cpft_rio import (
    TimelyCPFTRiOFilter,
)
from crate_anon.ancillary.timely_project.timely_filter_systmone import (
    TimelyCPFTGenericSystmOneFilter,
)
from crate_anon.anonymise.config import Config
from crate_anon.anonymise.dd import DataDictionary
from crate_anon.anonymise.ddr import DataDictionaryRow

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

FILTER_INFO_CHOICES = {
    # name, class
    "CPFT_RiO": TimelyCPFTRiOFilter,
    "CPFT_GenericSystmOne": TimelyCPFTGenericSystmOneFilter
}  # type: Dict[str, Type[TimelyDDFilter]]


# =============================================================================
# Reporting decisions to the log
# =============================================================================

# Nasty global:
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


# =============================================================================
# Deciding what to keep
# =============================================================================

def keep(row: DataDictionaryRow,
         inclusion_tables: List[TableCriterion],
         exclusion_tables: List[TableCriterion],
         exclusion_fields: List[FieldCriterion],
         system_tables_lower: List[str],
         scrub_src_tables_lower: List[str]) -> Optional[DataDictionaryRow]:
    """
    Filters each row. (Each row represents a source column/field.)

    - Always include anonymisation tables, matching
      ``scrub_src_tables_lower``.
    - Always exclude tables matching ``exclusion_tables_compiled``.
    - Always exclude fields matching ``exclusion_fields_compiled``.
    - Then include rows whose table matches ``inclusion_tables_compiled``.
    - Then include all system (non-patient) tables, matching
      ``scrub_src_tables_lower``.
    - Then exclude anything not meeting those criteria.

    Returns the row itself to keep, or None to reject.
    """
    tablename = row.src_table
    table_lower = tablename.lower()
    row_modified = copy.copy(row)  # may or may not use it!

    def decide(keep_: bool, reason: str) -> Optional[DataDictionaryRow]:
        report(reason)
        if keep_:
            full_reason = f"[TIMELY autofilter: {reason}]"
            row_modified.comment = " ".join((
                row_modified.comment or "",
                full_reason
            ))
            return row_modified
        else:
            return None

    # -------------------------------------------------------------------------
    # Main decision log
    # -------------------------------------------------------------------------

    if any(et.table_match(tablename) for et in exclusion_tables):
        return decide(False, f"Excluding specifically: {tablename}")

    for ef in exclusion_fields:
        if ef.table_field_match(tablename, row.src_field):
            return decide(
                False,
                f"Excluding specifically: {tablename}.{row.src_field} "
                f"(stage {ef.stage} rule)"
            )

    for inc_table in inclusion_tables:
        if inc_table.table_match(tablename):
            return decide(
                True,
                f"INCLUDING specifically: {tablename} "
                f"(stage {inc_table.stage} rule)"
            )

    if table_lower in system_tables_lower:
        return decide(True, f"INCLUDING system table: {tablename}")

    if table_lower in scrub_src_tables_lower:
        # Although we include the table in the data dictionary, we "omit" all
        # rows from the final output (unless the user actively added the table
        # in a previous step), in which case we include or omit depending on
        # the original data dictionary.
        row_modified.omit = True
        log.debug(f"For {tablename}.{row.src_field}, "
                  f"setting 'omit' flag to True")
        return decide(True, f"INCLUDING FOR ANONYMISATION: {tablename}")

    # Default:
    return decide(False, f"Excluding by default: {tablename}")


# =============================================================================
# File handling
# =============================================================================

def filter_dd(filter_info: TimelyDDFilter,
              input_filename: str,
              output_filename: str,
              stage: int) -> None:
    """
    Reads a data dictionary, filters it, and writes the output.
    """
    assert 1 <= stage <= N_STAGES
    log.info(f"Processing CPFT RiO data dictionary for TIMELY Stage {stage}")
    log.info(f"Reading data dictionary: {input_filename}")
    # We don't care about the actual config, so we use a mock one:
    config = Config(mock=True, open_databases=False)
    dd = DataDictionary.create_from_file(
        input_filename,
        config,
        check_valid=False,
        override_dialect=mssql_server_dialect
    )

    # Autodetect anonymisation (scrub-source) tables. We'll include them.
    scrub_src_tables_lower = [
        table.lower()
        for table in dd.get_tables_w_scrub_src()
    ]
    log.debug(f"scrub_src_tables_lower: {scrub_src_tables_lower}")

    # Autodetect system tables (those with no patient). We'll include them.
    system_tables_lower = [
        table.lower()
        for table in dd.get_tables_w_no_pt_info()
    ]
    log.debug(f"system_tables_lower: {system_tables_lower}")

    # Exclusion and inclusion tables.
    inclusion_tables = [
        t for t in filter_info.staged_include_tables
        if stage >= t.stage
        # "Include from t.stage or beyond."
    ]
    exclusion_fields = [
        f for f in filter_info.staged_exclude_fields
        if stage <= f.stage
        # "Exclude before and up to/including t.stage."
    ]

    def keep_modify_row(row: DataDictionaryRow) -> Optional[DataDictionaryRow]:
        return keep(
            row=row,
            inclusion_tables=inclusion_tables,
            exclusion_tables=filter_info.exclude_tables,
            exclusion_fields=exclusion_fields,
            system_tables_lower=system_tables_lower,
            scrub_src_tables_lower=scrub_src_tables_lower
        )

    log.info(f"Filtering. Starting with {dd.n_rows} rows...")
    dd.remove_rows_by_modifying_filter(keep_modify_row)
    log.info(f"... ending with {dd.n_rows} rows.")
    log.info(f"Writing data dictionary: {output_filename}")
    dd.write(output_filename)


# =============================================================================
# Command-line handling
# =============================================================================

def main() -> None:
    """
    Command-line entry point.
    """
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "input", type=str,
        help="Data dictionary file to read",
    )
    parser.add_argument(
        "output", type=str,
        help="Data dictionary file to write"
    )
    parser.add_argument(
        "--system", type=str, required=True,
        choices=sorted(FILTER_INFO_CHOICES.keys()),
        help="EHR system for which to translate the data dictionary"
    )
    parser.add_argument(
        "--stage", type=int,
        choices=list(range(1, N_STAGES + 1)), default=1,
        help="Approval stage."
    )
    parser.add_argument(
        "--nocolour", action="store_true",
        help="Disable colour in logs"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Be verbose"
    )
    args = parser.parse_args()

    loglevel = logging.DEBUG if args.verbose else logging.INFO
    if args.nocolour:
        logging.basicConfig(level=loglevel)
    else:
        main_only_quicksetup_rootlogger(level=loglevel)

    # Future: select different types of data dictionary here.
    filter_info_class = FILTER_INFO_CHOICES[args.system]
    filter_info = filter_info_class()

    filter_dd(
        filter_info=filter_info,
        input_filename=args.input,
        output_filename=args.output,
        stage=args.stage
    )


if __name__ == "__main__":
    main()
