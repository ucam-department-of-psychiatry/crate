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
import re
from typing import Dict, List, Optional, Pattern, Tuple

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from sqlalchemy.dialects.mssql.base import dialect as sql_server_dialect

from crate_anon.anonymise.config import Config
from crate_anon.anonymise.dd import DataDictionary
from crate_anon.anonymise.ddr import DataDictionaryRow

log = logging.getLogger(__name__)


# =============================================================================
# Regex convenience
# =============================================================================

def compile(r: str) -> Pattern:
    """
    Compiles a regex for case-insensitive use.
    """
    return re.compile(r, flags=re.IGNORECASE)


# =============================================================================
# Deciding about rows
# =============================================================================

# Approvals are in stages.

N_STAGES = 6

EXCLUDE_TABLE_REGEXES = [
    "cpft_core_assessment_v2_kcsa_children_in_household",  #  about people other than the patient  # noqa
]


# -----------------------------------------------------------------------------
# Stage 1: demographics, problem lists, diagnoses, safeguarding, contacts
# (e.g. referrals, contacts, discharge)
# -----------------------------------------------------------------------------

STAGE_1_INCLUDE_TABLE_REGEXES = [
    # Demographics
    "Client_Demographic_Details",  # basics
    "Client_Address_History",  # addresses blurred to LSOAs
    "Deceased",

    # Safeguarding
    "Client_Family",  # legal status codes, parental responsibility, etc.
    "ClientAlert",
    # ClientAlertRemovalReason is an example of a system table -- it doesn't
    # relate to a patient. We include those automatically.
    "RskRelatedIncidents",  # BUT SEE field exclusions
    "RskRelatedIncidentsRiskType",

    # Basic contacts, e.g. start/end of care plan
    "Client_CPA",  # care plan start/end dates
    "Client_GP",  # GP practice registration
    "Client_School",  # school attended
    "ClientGPMerged",  # when GP practices merge, we think

    # Diagnosis/problems
    "ClientOtherSmoker",  # smoking detail
    "ClientSmoking",  # more smoking detail
    # ClientSocialFactor -- no data
    "Diagnosis",  # ICD-10 diagnoses
    "SNOMED.*",  # SNOMED-coded problems

    # Referrals (basic info)
    "Referral.*",  # includes ReferralCoding = diagnosis for referral (+ teams etc.)  # noqa
]


# Note that "UserAssess*" is where all the local custom additions to RiO go.
# These are quite varied.

# -----------------------------------------------------------------------------
# Stage 2: detailed information about all service contacts, including
# professional types involved, outcome data, etc.
# -----------------------------------------------------------------------------

STAGE_2_INCLUDE_TABLE_REGEXES = STAGE_1_INCLUDE_TABLE_REGEXES + [
    "Client_Professional_Contacts",
    "ClientHealthCareProviderAssumed",

    # Inpatient activity (IMS = inpatient management system)
    "Ims.*",
    "Inpatient.*",
    "IPAms.*",

    # Mnt = Mental Health Act
    "Mnt.*",

    "ParentGuardianImport",  # outcome data
]


# -----------------------------------------------------------------------------
# Stage 3: prescribing data
# -----------------------------------------------------------------------------

STAGE_3_INCLUDE_TABLE_REGEXES = STAGE_2_INCLUDE_TABLE_REGEXES + [
    "Client_Allergies",  # for prescribing
    "Client_Medication",  # will be empty!
    "Client_Prescription",  # will be empty!
]


# -----------------------------------------------------------------------------
# Stage 4: test results, other health assessments, other clinical info
# -----------------------------------------------------------------------------

STAGE_4_INCLUDE_TABLE_REGEXES = STAGE_3_INCLUDE_TABLE_REGEXES + [
    "Client_Physical_Details",  # e.g. head circumference
    "ClientMaternalDetail",  # patients who are mothers
    "ClientPhysicalDetailMerged",  # e.g. height, weight
]


# -----------------------------------------------------------------------------
# Stage 5: (structured) info on care plans etc.
# -----------------------------------------------------------------------------

STAGE_5_INCLUDE_TABLE_REGEXES = STAGE_4_INCLUDE_TABLE_REGEXES + [
    # Care plans, Care Plan Approach, care coordination
    "Care_Plan.*",
    "CarePlan.*",
    "CareCoordinatorOccupation",
    "CPA.*"
]


# -----------------------------------------------------------------------------
# Stage 6: de-identified free text
# -----------------------------------------------------------------------------

STAGE_6_INCLUDE_TABLE_REGEXES = STAGE_5_INCLUDE_TABLE_REGEXES + [
    "Clinical_Documents",
    "CPFT_Core_Assessment.*",
    "Progress_Note",
    "RskRelatedIncidents",
    "UserAssessCAMH",  # CAMH-specific assessments (e.g. questionnaires) -- can have free-text comments.  # noqa
]


# -----------------------------------------------------------------------------
# Specific fields
# -----------------------------------------------------------------------------
# Specific fields to exclude that would otherwise be included.
# List of (tablename, fieldname) regex string tuples.

STAGE_6_EXCLUDE_FIELDS = []  # type: List[Tuple[str, str]]
STAGE_5_EXCLUDE_FIELDS = STAGE_6_EXCLUDE_FIELDS + [
    # "exclude at stage 5 or earlier"
    ("RskRelatedIncidents", "Text")
]  # type: List[Tuple[str, str]]
STAGE_4_EXCLUDE_FIELDS = STAGE_5_EXCLUDE_FIELDS
STAGE_3_EXCLUDE_FIELDS = STAGE_4_EXCLUDE_FIELDS
STAGE_2_EXCLUDE_FIELDS = STAGE_3_EXCLUDE_FIELDS
STAGE_1_EXCLUDE_FIELDS = STAGE_2_EXCLUDE_FIELDS


# -----------------------------------------------------------------------------
# Putting it together
# -----------------------------------------------------------------------------

STAGE_INCLUSION_TABLES = {
    # dictionary mapping stage number to inclusion list
    1: STAGE_1_INCLUDE_TABLE_REGEXES,
    2: STAGE_2_INCLUDE_TABLE_REGEXES,
    3: STAGE_3_INCLUDE_TABLE_REGEXES,
    4: STAGE_4_INCLUDE_TABLE_REGEXES,
    5: STAGE_5_INCLUDE_TABLE_REGEXES,
    6: STAGE_6_INCLUDE_TABLE_REGEXES,
}  # type: Dict[int, List[str]]

STAGE_EXCLUSION_FIELDS = {
    # dictionary mapping stage number to (table, field) tuple
    1: STAGE_1_EXCLUDE_FIELDS,
    2: STAGE_2_EXCLUDE_FIELDS,
    3: STAGE_3_EXCLUDE_FIELDS,
    4: STAGE_4_EXCLUDE_FIELDS,
    5: STAGE_5_EXCLUDE_FIELDS,
    6: STAGE_6_EXCLUDE_FIELDS,
}  # type: Dict[int, List[Tuple[str, str]]]


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
         inclusion_tables_compiled: List[Pattern],
         exclusion_tables_compiled: List[Pattern],
         exclusion_fields_compiled: List[Tuple[Pattern, Pattern]],
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

    for r in exclusion_tables_compiled:
        if r.match(tablename):
            report(f"Excluding specifically: {tablename}")
            return None

    for bad_tablename, bad_fieldname in exclusion_fields_compiled:
        if (bad_tablename.match(tablename)
                and bad_fieldname.match(row.src_field)):
            report(f"Excluding specifically: {tablename}.{row.src_field}")
            return None

    for r in inclusion_tables_compiled:
        if r.match(tablename):
            report(f"INCLUDING specifically: {tablename}")
            return row

    if table_lower in system_tables_lower:
        report(f"INCLUDING system table: {tablename}")
        return row

    if table_lower in scrub_src_tables_lower:
        report(f"INCLUDING FOR ANONYMISATION: {tablename}")
        # ... but although we include the table in the data dictionary, we
        # "omit" all rows from the final output (unless the user actively added
        # the table in a previous step).
        row_modified = copy.copy(row)
        row_modified.omit = True
        log.debug(f"For {tablename}.{row.src_field}, "
                  f"setting 'omit' flag to True")
        return row_modified

    # Default:
    report(f"Excluding by default: {tablename}")
    return None


# =============================================================================
# File handling
# =============================================================================

def filter_dd(input_filename: str,
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
        override_dialect=sql_server_dialect
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
    exclusion_tables_compiled = [compile(x) for x in EXCLUDE_TABLE_REGEXES]
    inclusion_tables = STAGE_INCLUSION_TABLES[stage]
    inclusion_tables_compiled = [compile(x) for x in inclusion_tables]
    exclusion_fields_compiled = [
        (compile(_tablename), compile(_fieldname))
        for _tablename, _fieldname in STAGE_EXCLUSION_FIELDS[stage]
    ]

    def keep_modify_row(row: DataDictionaryRow) -> Optional[DataDictionaryRow]:
        return keep(
            row=row,
            inclusion_tables_compiled=inclusion_tables_compiled,
            exclusion_tables_compiled=exclusion_tables_compiled,
            exclusion_fields_compiled=exclusion_fields_compiled,
            system_tables_lower=system_tables_lower,
            scrub_src_tables_lower=scrub_src_tables_lower
        )

    log.info(f"Filtering. Starting with {dd.n_rows} rows...")
    dd.remove_rows_by_modifying_filter(keep_modify_row)
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
        "--nocolour", action="store_true",
        help="Disable colour in logs"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Be verbose"
    )
    parser.add_argument(
        "--stage", type=int,
        choices=list(range(1, N_STAGES + 1)), default=1,
        help="Approval stage."
    )
    args = parser.parse_args()

    loglevel = logging.DEBUG if args.verbose else logging.INFO
    if args.nocolour:
        logging.basicConfig(level=loglevel)
    else:
        main_only_quicksetup_rootlogger(level=loglevel)

    filter_dd(
        input_filename=args.input,
        output_filename=args.output,
        stage=args.stage
    )


if __name__ == "__main__":
    main()
