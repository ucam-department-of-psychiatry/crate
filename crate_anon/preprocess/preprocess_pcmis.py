#!/usr/bin/env python
# preprocess/preprocess_pcmis.py

INCOMPLETE_DO_NOT_USE

"""
===============================================================================
    Copyright (C) 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

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

===============================================================================
PCMIS table structure
===============================================================================
- No proper documentation, but the structure is clear.
- See pcmis_information_schema.ods


- PatientDetails

    PatientID -- PK; patient-defining field; VARCHAR(100)
    FirstName
    LastName
    NHSNumber
    ...

- Other per-patient things: Patient*

- CasesAll

    CaseNumber -- appears to be unique; same #records as ReferralDetails

- Many other per-case things: Case*

    CaseNumber -- FK to CasesAll/ReferralDetails
    
- Group things: linked to cases via GroupMember

- Carers: from PatientCarerDetails (CarerNumber, PatientID)
- Children: from PatientChildDetails (ChildNumber, PatientID)

- ReferralDetails

    CaseNumber -- appears to be unique; same #records as CasesAll
    PatientID -- not unique
    PrimaryDiagnosis (e.g. 'F41.1')

- Non-patient stuff we'll filter out:

    pcmis_UserProfiles
    Users

"""


import argparse
import logging
from typing import Any, List, Optional

from sqlalchemy import (
    create_engine,
    MetaData,
)
from sqlalchemy.engine import Engine
from sqlalchemy.schema import Column, Table
from sqlalchemy.sql.sqltypes import BigInteger, Integer

from crate_anon.anonymise.constants import CHARSET
from crate_anon.common.debugfunc import pdb_run
from crate_anon.common.logsupport import configure_logger_for_colour
from crate_anon.common.sql import (
    add_columns,
    add_indexes,
    assert_view_has_same_num_rows,
    create_view,
    drop_columns,
    drop_indexes,
    drop_view,
    ensure_columns_present,
    execute,
    get_column_names,
    get_table_names,
    get_view_names,
    set_print_not_execute,
    sql_fragment_cast_to_int,
    ViewMaker,
)
from crate_anon.common.sqla import (
    get_single_int_pk_colname,
    get_single_int_autoincrement_colname,
    hack_in_mssql_xml_type,
    make_bigint_autoincrement_column,
)
from crate_anon.preprocess.rio_ddgen import (
    DDHint,
    get_rio_dd_settings,
)

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

CRATE_COL_PK = "crate_pk"
CRATE_COL_PCMIS_NUMBER = "crate_pcmis_number"
CRATE_COL_NHS_NUMBER = "crate_nhs_number_int"
MASTER_PATIENT_TABLE = "PatientDetails"
PCMIS_COL_PATIENT_ID_COL = "PatientId"

PCMIS_DRAFT_DDGEN = """
"""


# =============================================================================
# Typical instructions with which to draft a PCMIS data dictionary
# automatically
# =============================================================================

def get_pcmis_dd_settings(ddhint: DDHint) -> str:
    return """
ddgen_omit_by_default = True

ddgen_omit_fields =

ddgen_include_fields = #
    # -------------------------------------------------------------------------
    # RCEP core views:
    # -------------------------------------------------------------------------
    Care_Plan_Index.*
    Care_Plan_Interventions.*
    Care_Plan_Problems.*
    Client_Address_History.*
    Client_Alternative_ID.*
    Client_Allergies.*
    Client_Communications_History.*
    Client_CPA.*
    Client_Demographic_Details.*
    Client_Family.*
    Client_GP_History.*
    Client_Medication.*
    Client_Name_History.*
    Client_Personal_Contacts.*
    Client_Physical_Details.*
    Client_Prescription.*
    Client_Professional_Contacts.*
    Client_School.*
    CPA_CareCoordinator.*
    CPA_Review.*
    Diagnosis.*
    Inpatient_Stay.*
    Inpatient_Leave.*
    Inpatient_Movement.*
    Inpatient_Named_Nurse.*
    Inpatient_Sleepover.*
    Referral.*
    Progress_Notes.*
    Referral_Staff_History.*
    Referral_Team_History.*
    Referral_Waiting_Status_History.*
    # -------------------------------------------------------------------------
    # Non-core:
    # -------------------------------------------------------------------------
    CPFT_*.*  # all fields in "CPFT_*" views

ddgen_allow_no_patient_info = False

ddgen_per_table_pid_field = crate_rio_number

ddgen_add_per_table_pids_to_scrubber = False

ddgen_master_pid_fieldname = crate_nhs_number_int
    # ... is in Client_Demographic_Details view

ddgen_table_blacklist = #
    # -------------------------------------------------------------------------
    # Blacklist: Prefixes: groups of tables; individual tables
    # -------------------------------------------------------------------------
    Agresso*  # Agresso [sic] module (comms to social worker systems)
    ADT*  # ?admit/discharge/transfer messages (see codes in ADTMessage)
    Ams*  # Appointment Management System (Ams) module
    Audit*  # RiO Audit Trail
    CDSContract*  # something to do with commissioner contracts
    Chd*  # Child development (interesting, but lots of tables and all empty)
    Client  # RiO 5; superseded by ClientIndex (and then view Client_Demographic_Details); ?runs alongside as partial duplicate?
    ClientAddressHistory  # defunct according to RIO 6.2 docs
    ClientAddressMerged  # defunct according to RIO 6.2 docs
    ClientChild*  # child info e.g. birth/immunisation (interesting, but several tables and all empty)
    ClientCommunityDomain # defunct according to RIO 6.2 docs
    ClientFamily  # contains only a comment; see ClientFamilyLink instead
    ClientMerge*  # record of admin events (merging of client records)
    ClientPhoto*  # no use to us or identifiable!
    ClientRestrictedRecord*  # ? but admin
    Con*  # Contracts module
    DA*  # Drug Administration within EP
    DemAuditTrail  # not in v6.2 docs; ?audit trail for demographics
    DgnDiagnosis  # "Obsolete"; see DiagnosisClient
    DS*  # Drug Service within EP
    dtoElectoralWardPCLookup  # we do our own geography; 2.5m records
    EP*  # E-Prescribing (EP) module, which we don't have
    #   ... mostly we don't have it, but we may have EPClientAllergies etc.
    #   ... so see whitelist too
    ESRImport  # user-to-?role map? Small and system.
    ExternalSystem*  # system
    GenChd*  # lookup codes for Chd*
    GenCon*  # lookup codes for Con*
    GenDiagnosis  # "Obsolete"
    GenError*  # system
    GenExtendedPostcode  # we provide our own geography lookups; 5m records
    GenExtract*  # details of reporting extracts
    GenHCPTemplateDetails  # HCP diary template
    GenIDSeed  # system (counters for different ID types)
    GenLicenseKeys  # system; NB shows what components are licensed!
    GenNumbers  # just a list of integers
    GenPostcodeGeographicDataMappings  # as above, we do our own geography; 2.5m records
    GenPrinter*  # printers
    GenToDoList  # user to-do list items/notifications
    gridall  # same number of records as dtoElectoralWardPCLookup; also geography;
    KP90ErrorLog  # error log for KP90 report; http://www.hscic.gov.uk/datacollections/kp90
    LR*  # Legitimate Relationships module
    Meeting*  # Meetings module
    Mes*  # messaging
    MonthlyPlanner*  # system
    PSS*  # Prevention, Screening & Surveillance (PSS)
    RioPerformanceTimings  # system
    RR*  # Results Reporting (e.g. laboratories, radiology)
    #   ... would be great, but we don't have it
    RTT*  # RTT* = Referral-to-Treatment (RTT) data collection (see NHS England docs)
    SAF*  # SAF* = system; looks like details of tablet devices
    Scheduler*  # Scheduler* = Scheduler module (for RiO computing)
    Sec*  # Security? Definitely RiO internal stuff.
    SPINE*  # system
    SPRExternalNotification  # system?
    tbl*  # records of changes to tables?
    TeamPlanner*  # system
    Temp*  # system
    umt*  # system
    Wfl*  # workflow
    WL*  # Waiting lists (WL) module
    view_AuditTrailPurge  # system; e.g. 96m records
    # -------------------------------------------------------------------------
    # Blacklist: Middle bits, suffixes
    # -------------------------------------------------------------------------
    *Access*  # system access controls
    *Backup  # I'm guessing backups...
    *Cache*  # system
    *Lock*  # system
    *Timeout*  # system
    # -------------------------------------------------------------------------
    # Blacklist: CPFT custom
    # -------------------------------------------------------------------------
    CDL_OUTDATEDPATIENTS_TWI  # RiO to CPFT 'M' number mapping, but we will use NHS number
    # -------------------------------------------------------------------------
    # Blacklist: Views supersede
    # Below here, we have other tables suppressed because CRATE's views offer
    # more comprehensive alternatives
    # -------------------------------------------------------------------------
    {suppress_tables}

# USEFUL TABLES (IN CPFT INSTANCE) INCLUDE:
# =========================================
# Assessment* = includes maps of non-core assessments (see e.g. AssessmentIndex)
# CDL_OUTDATEDPATIENTS_TWI = map from TWI (trust-wide identifier) to old CPFT M number
# UserAssess* = non-core assessments themselves
# UserMaster* = lookup tables for non-core assessments

ddgen_table_whitelist = #
    # -------------------------------------------------------------------------
    # Whitelist: Prefixes: groups of tables
    # -------------------------------------------------------------------------
    EPClientAllergy*  # Allergy details within EP module
    # -------------------------------------------------------------------------
    # Whitelist: Suffixes
    # -------------------------------------------------------------------------
    *_crate  # Views added by CRATE
    # -------------------------------------------------------------------------
    # Whitelist: Individual tables
    # -------------------------------------------------------------------------
    EPReactionType  # Allergy reaction type details within EP module

ddgen_table_require_field_absolute = #
    # All tables/fields must have crate_pk
    {CRATE_COL_PK}

ddgen_table_require_field_conditional = #
    # If a table/view has ClientID, it must have crate_rio_number
    {RIO_COL_PATIENT_ID}, {CRATE_COL_RIO_NUMBER}

ddgen_field_blacklist = #
    {RIO_COL_PATIENT_ID}  # replaced by crate_rio_number (which is then pseudonymised)
    *Soundex  # identifying 4-character code; https://msdn.microsoft.com/en-us/library/ms187384.aspx
    Spine*  # NHS Spine identifying codes

ddgen_field_whitelist =

ddgen_pk_fields = crate_pk

ddgen_constant_content = False

ddgen_constant_content_tables =

ddgen_nonconstant_content_tables =

ddgen_addition_only = False

ddgen_addition_only_tables = #
    UserMaster*  # Lookup tables for non-core - addition only?

ddgen_deletion_possible_tables =

ddgen_pid_defining_fieldnames = Client_Demographic_Details.crate_rio_number

ddgen_scrubsrc_patient_fields = # several of these:
    # ----------------------------------------------------------------------
    # Original RiO tables (some may be superseded by views; list both here;
    # if the table is blacklisted anyway, it doesn't matter).
    # ----------------------------------------------------------------------
    AmsReferral.DischargeAddressLine*  # superseded by view Referral
    AmsReferral.DischargePostCode  # superseded by view Referral
    ClientAddress.AddressLine*  # superseded by view Client_Address_History
    ClientAddress.PostCode  # superseded by view Client_Address_History
    ClientAlternativeID.ID  # superseded by view Client_Alternative_ID
    ClientIndex.crate_pk  # superseded by view Client_Demographic_Details
    ClientIndex.DateOfBirth  # superseded by view Client_Demographic_Details
    ClientIndex.DaytimePhone  # superseded by view Client_Demographic_Details
    ClientIndex.EMailAddress  # superseded by view Client_Demographic_Details
    ClientIndex.EveningPhone  # superseded by view Client_Demographic_Details
    ClientIndex.Firstname  # superseded by view Client_Demographic_Details
    ClientIndex.MobilePhone  # superseded by view Client_Demographic_Details
    ClientIndex.NINumber  # superseded by view Client_Demographic_Details
    ClientIndex.OtherAddress  # superseded by view Client_Demographic_Details
    ClientIndex.SpineID  # superseded by view Client_Demographic_Details
    ClientIndex.Surname  # superseded by view Client_Demographic_Details
    ClientName.GivenName*  # superseded by view Client_Name_History
    ClientName.Surname  # superseded by view Client_Name_History
    ClientTelecom.Detail  # superseded by view Client_Communications_History
    ImsEvent.DischargeAddressLine*  # superseded by view Inpatient_Stay
    ImsEvent.DischargePostCode*  # superseded by view Inpatient_Stay
    ImsEventLeave.AddressLine*  # superseded by view Inpatient_Leave
    ImsEventLeave.PostCode  # superseded by view Inpatient_Leave
    # ----------------------------------------------------------------------
    # Views
    # ----------------------------------------------------------------------
    Client_Address_History.Address_Line_*
    Client_Address_History.Post_Code
    Client_Alternative_ID.ID
    Client_Communications_History.crate_telephone
    Client_Communications_History.crate_email_address
    Client_Demographic_Details.crate_rio_number
    Client_Demographic_Details.NHS_Number
    Client_Demographic_Details.Firstname
    Client_Demographic_Details.Surname
    Client_Demographic_Details.Date_of_Birth
    Client_Demographic_Details.*Phone
    Client_Demographic_Details.Superseding_NHS_Number
    Client_Name_History.Given_Name_*
    Client_Name_History.Family_Name
    Inpatient_Leave.Address_Line*
    Inpatient_Leave.PostCode
    Inpatient_Stay.Discharge_Address_Line_*
    Inpatient_Stay.Discharge_Post_Code*
    Referral.Discharge_Address_Line_*
    Referral.Discharge_Post_Code*
    {VIEW_ADDRESS_WITH_GEOGRAPHY}.AddressLine*  # superseded by other view Client_Address_History
    {VIEW_ADDRESS_WITH_GEOGRAPHY}.PostCode  # superseded by other view Client_Address_History

ddgen_scrubsrc_thirdparty_fields = # several:
    # ----------------------------------------------------------------------
    # Original RiO tables (some may be superseded by views; list both here)
    # ----------------------------------------------------------------------
    # ClientFamilyLink.RelatedClientID  # superseded by view Client_Family
    ClientContact.Surname  # superseded by view Client_Personal_Contacts
    ClientContact.Firstname  # superseded by view Client_Personal_Contacts
    ClientContact.AddressLine*  # superseded by view Client_Personal_Contacts
    ClientContact.PostCode  # superseded by view Client_Personal_Contacts
    ClientContact.*Phone  # superseded by view Client_Personal_Contacts
    ClientContact.EmailAddress  # superseded by view Client_Personal_Contacts
    ClientContact.NHSNumber  # superseded by view Client_Personal_Contacts
    # ClientIndex.MainCarer  # superseded by view Client_Demographic_Details
    # ClientIndex.OtherCarer  # superseded by view Client_Demographic_Details
    # ----------------------------------------------------------------------
    # RCEP/CRATE views
    # ----------------------------------------------------------------------
    Client_Personal_Contacts.Family_Name
    Client_Personal_Contacts.Given_Name
    Client_Personal_Contacts.Address_Line_*
    Client_Personal_Contacts.Post_Code
    Client_Personal_Contacts.*Phone
    Client_Personal_Contacts.Email_Address
    Client_Personal_Contacts.NHS_Number

ddgen_scrubsrc_thirdparty_xref_pid_fields = # several:
    # ----------------------------------------------------------------------
    # Original RiO tables (some may be superseded by views; list both here)
    # ----------------------------------------------------------------------
    # none; these are not integer:
    # ClientFamilyLink.RelatedClientID  # superseded by view Client_Family
    # ClientIndex.MainCarer  # superseded by view Client_Demographic_Details
    # ClientIndex.OtherCarer  # superseded by view Client_Demographic_Details
    # ----------------------------------------------------------------------
    # RCEP/CRATE views
    # ----------------------------------------------------------------------
    Client_Demographic_Details.Main_Carer
    Client_Demographic_Details.Other_Carer
    Client_Family.Related_Client_ID

ddgen_required_scrubsrc_fields = # several:
    Client_Demographic_Details.Date_Of_Birth
    Client_Name_History.Given_Name_1
    Client_Name_History.Family_Name

ddgen_scrubmethod_code_fields = # variants:
    *PostCode*
    *Post_Code*
    NINumber
    National_Insurance_Number
    ClientAlternativeID.ID
    Client_Alternative_ID.ID

ddgen_scrubmethod_date_fields = *Date*

ddgen_scrubmethod_number_fields = #
    *Phone*
    *NNN*
    *NHS_Number*

ddgen_scrubmethod_phrase_fields = *Address*

ddgen_safe_fields_exempt_from_scrubbing =

    # RiO mostly uses string column lengths of 4, 10, 20, 40, 80, 500,
    # unlimited. So what length is the minimum for "free text"?
    # Comments are 500. Lots of 80-length fields are lookup descriptions.
    # (Note that many scrub-SOURCE fields are of length 80, e.g. address
    # fields, but they need different special handling.)
ddgen_min_length_for_scrubbing = 81

ddgen_truncate_date_fields = Client_Demographic_Details.Date_Of_Birth

ddgen_filename_to_text_fields = Clinical_Documents.Path

ddgen_binary_to_text_field_pairs =

ddgen_skip_row_if_extract_text_fails_fields = Clinical_Documents.Path

ddgen_index_fields =

ddgen_allow_fulltext_indexing = True

ddgen_force_lower_case = False

ddgen_convert_odd_chars_to_underscore = True
    """.format(  # noqa
        CRATE_COL_PK=CRATE_COL_PK,
        CRATE_COL_RIO_NUMBER=CRATE_COL_RIO_NUMBER,
        RIO_COL_PATIENT_ID=RIO_COL_PATIENT_ID,
        suppress_tables="\n    ".join(ddhint.get_suppressed_tables()),
        VIEW_ADDRESS_WITH_GEOGRAPHY=VIEW_ADDRESS_WITH_GEOGRAPHY,
    )


# =============================================================================
# Generic table processors
# =============================================================================

def is_per_case_table(table: Table) -> bool:
    pass


# =============================================================================
# Specific table processors
# =============================================================================


# =============================================================================
# PCMIS views
# =============================================================================



# =============================================================================
# Geography views
# =============================================================================

def add_postcode_geography_view(engine: Engine,
                                progargs: Any,
                                ddhint: DDHint) -> None:  # ddhint modified
    # Re-read column names, as we may have inserted some recently by hand that
    # may not be in the initial metadata.
    if progargs.rio:
        addresstable = RIO_TABLE_ADDRESS
        rio_postcodecol = RIO_COL_POSTCODE
    else:
        addresstable = RCEP_TABLE_ADDRESS
        rio_postcodecol = RCEP_COL_POSTCODE
    orig_column_names = get_column_names(engine, tablename=addresstable,
                                         sort=True)

    # Remove any original column names being overridden by new ones.
    # (Could also do this the other way around!)
    geogcols_lowercase = [x.lower() for x in progargs.geogcols]
    orig_column_names = [x for x in orig_column_names
                         if x.lower() not in geogcols_lowercase]

    orig_column_specs = [
        "{t}.{c}".format(t=addresstable, c=col)
        for col in orig_column_names
    ]
    geog_col_specs = [
        "{db}.{t}.{c}".format(db=progargs.postcodedb,
                              t=ONSPD_TABLE_POSTCODE,
                              c=col)
        for col in sorted(progargs.geogcols, key=lambda x: x.lower())
    ]
    overlap = set(orig_column_names) & set(progargs.geogcols)
    if overlap:
        raise ValueError(
            "Columns overlap: address table contains columns {}; "
            "geogcols = {}; overlap = {}".format(
                orig_column_names, progargs.geogcols, overlap))
    ensure_columns_present(engine, tablename=addresstable, column_names=[
        rio_postcodecol])
    select_sql = """
        SELECT {origcols},
            {geogcols}
        FROM {addresstable}
        LEFT JOIN {pdb}.{pcdtab}
        ON {addresstable}.{rio_postcodecol} = {pdb}.{pcdtab}.pcds
        -- RCEP, and presumably RiO, appear to use the ONS pcds format, of
        -- 2-4 char outward code; space; 3-char inward code.
        -- If this fails, use this slower version:
        -- ON REPLACE({addresstable}.{rio_postcodecol},
        --            ' ',
        --            '') = {pdb}.{pcdtab}.pcd_nospace
    """.format(
        addresstable=addresstable,
        origcols=",\n            ".join(orig_column_specs),
        geogcols=",\n            ".join(geog_col_specs),
        pdb=progargs.postcodedb,
        pcdtab=ONSPD_TABLE_POSTCODE,
        rio_postcodecol=rio_postcodecol,
    )
    create_view(engine, VIEW_ADDRESS_WITH_GEOGRAPHY, select_sql)
    assert_view_has_same_num_rows(engine, addresstable,
                                  VIEW_ADDRESS_WITH_GEOGRAPHY)
    ddhint.suppress_table(addresstable)


# =============================================================================
# Table action selector
# =============================================================================

def process_table(table: Table, engine: Engine, progargs: Any) -> None:
    tablename = table.name
    column_names = table.columns.keys()
    log.debug("TABLE: {}; COLUMNS: {}".format(tablename, column_names))
    if progargs.rio:
        patient_table_indicator_column = get_rio_patient_id_col(table)
    else:  # RCEP:
        patient_table_indicator_column = RCEP_COL_PATIENT_ID

    is_patient_table = (patient_table_indicator_column in column_names or
                        tablename == progargs.full_prognotes_table)
    # ... special for RCEP/CPFT, where a RiO table (with different patient ID
    # column) lives within an RCEP database.
    if progargs.drop_danger_drop:
        # ---------------------------------------------------------------------
        # DROP STUFF! Opposite order to creation (below)
        # ---------------------------------------------------------------------
        # Specific
        if tablename == progargs.master_patient_table:
            drop_for_master_patient_table(table, engine)
        elif tablename == progargs.full_prognotes_table:
            drop_for_progress_notes(table, engine)
        elif progargs.rio and tablename == RIO_TABLE_CLINICAL_DOCUMENTS:
            drop_for_clindocs_table(table, engine)
        # Generic
        if is_patient_table:
            drop_for_patient_table(table, engine)
        else:
            drop_for_nonpatient_table(table, engine)
    else:
        # ---------------------------------------------------------------------
        # CREATE STUFF!
        # ---------------------------------------------------------------------
        # Generic
        if is_patient_table:
            process_patient_table(table, engine, progargs)
        else:
            process_nonpatient_table(table, engine, progargs)
        # Specific
        if tablename == progargs.master_patient_table:
            process_master_patient_table(table, engine, progargs)
        elif progargs.rio and tablename == RIO_TABLE_CLINICAL_DOCUMENTS:
            process_clindocs_table(table, engine, progargs)
        elif tablename == progargs.full_prognotes_table:
            process_progress_notes(table, engine, progargs)


def process_all_tables(engine: Engine,
                       metadata: MetaData,
                       progargs: Any) -> None:
    for table in sorted(metadata.tables.values(),
                        key=lambda t: t.name.lower()):
        process_table(table, engine, progargs)


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        # formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Alters a PCMIS database to be suitable for CRATE.")
    parser.add_argument("--url", required=True, help="SQLAlchemy database URL")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose")
    parser.add_argument(
        "--print", action="store_true",
        help="Print SQL but do not execute it. (You can redirect the printed "
             "output to create an SQL script.")
    parser.add_argument("--echo", action="store_true", help="Echo SQL")

    parser.add_argument(
        "--drop-danger-drop", action="store_true",
        help="REMOVES new columns and indexes, rather than creating them. "
             "(There's not very much danger; no real information is lost, but "
             "it might take a while to recalculate it.)")

    parser.add_argument(
        "--debug-skiptables", action="store_true",
        help="DEBUG-ONLY OPTION. Skip tables (view creation only)")

    parser.add_argument(
        "--postcodedb",
        help='Specify database (schema) name for ONS Postcode Database (as '
             'imported by CRATE) to link to addresses as a view. With SQL '
             'Server, you will have to specify the schema as well as the '
             'database; e.g. "--postcodedb ONS_PD.dbo"')
    parser.add_argument(
        "--geogcols", nargs="*", default=DEFAULT_GEOG_COLS,
        help="List of geographical information columns to link in from ONS "
             "Postcode Database. BEWARE that you do not specify anything too "
             "identifying. Default: {}".format(' '.join(DEFAULT_GEOG_COLS)))

    parser.add_argument(
        "--settings-filename",
        help="Specify filename to write draft ddgen_* settings to, for use in "
             "a CRATE anonymiser configuration file.")

    progargs = parser.parse_args()

    rootlogger = logging.getLogger()
    configure_logger_for_colour(
        rootlogger, level=logging.DEBUG if progargs.verbose else logging.INFO)

    log.info("CRATE in-place preprocessor for PCMIS databases")
    safeargs = {k: v for k, v in vars(progargs).items() if k != 'url'}
    log.debug("args (except url): {}".format(repr(safeargs)))

    if progargs.postcodedb and not progargs.geogcols:
        raise ValueError(
            "If you specify postcodedb, you must specify some geogcols")

    set_print_not_execute(progargs.print)

    hack_in_mssql_xml_type()

    engine = create_engine(progargs.url, echo=progargs.echo,
                           encoding=CHARSET)
    metadata = MetaData()
    metadata.bind = engine
    log.info("Database: {}".format(repr(engine.url)))  # ... repr hides p/w
    log.debug("Dialect: {}".format(engine.dialect.name))

    log.info("Reflecting (inspecting) database...")
    metadata.reflect(engine)
    log.info("... inspection complete")

    ddhint = DDHint()

    if progargs.drop_danger_drop:
        # Drop views (and view-induced table indexes) first
        drop_pcmis_views(engine, metadata, progargs, ddhint)
        drop_view(engine, VIEW_ADDRESS_WITH_GEOGRAPHY)
        if not progargs.debug_skiptables:
            process_all_tables(engine, metadata, progargs)
    else:
        # Tables first, then views
        if not progargs.debug_skiptables:
            process_all_tables(engine, metadata, progargs)
        if progargs.postcodedb:
            add_postcode_geography_view(engine, progargs, ddhint)
        create_pcmis_views(engine, metadata, progargs, ddhint)

    if progargs.settings_filename:
        with open(progargs.settings_filename, 'w') as f:
            print(get_rio_dd_settings(ddhint), file=f)


if __name__ == '__main__':
    pdb_run(main)
