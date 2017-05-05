#!/usr/bin/env python
# preprocess/preprocess_pcmis.py

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
No proper documentation, but the structure is clear.
See pcmis_information_schema.ods

- PatientDetails

    PatientID -- PK; patient-defining field; VARCHAR(100)
    FirstName
    LastName
    NHSNumber -- VARCHAR(100)
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

===============================================================================
Decisions re database keys and anonymisation
===============================================================================

For RiO, we had integer patient IDs but mangled into a text format. So there
were distinct performance advantages in making an integer version. For PCMIS,
patient IDs look like 'JC000001', 'SB000001' (where the letters are unrelated
to patients' initials; I'm not sure what they refer to). There are numerical
overlaps if you ignore the letters. So there is no neat integer mapping; we'd
be inventing an arbitrary new key if we added one.

So the tradeoff is simplicity (keep textual PK for patients) versus speed
(parallel processing based on an integer operation). It's natural to think of
an integer hash of a string, but this hash has to operate in the SQL
domain, be portable, and produce an integer (so SQL Server's HASHBYTES is of 
no use. At present (2017-05-02), our PCMIS copy has ~53,000 patients in, and
there are lots of tables with patients in.

Therefore, DECISION: create an integer PK.

However, we could do this deterministically. Since the length is fixed, and the
numerical part goes up to 999999, and the letters are always upper case -- ah,
no, there are some like <digit><letter>999999. But 0-99 would be fine.

    SELECT (
        (ASCII(SUBSTRING(PatientID, 1, 1))) * 100000000 +
        (ASCII(SUBSTRING(PatientID, 2, 1))) * 1000000 +
        CAST(SUBSTRING(PatientID, 3, 6) AS BIGINT)
    ) AS patient_id_int
    FROM PatientDetails

If we're using SQLAlchemy, then use things like func.substr instead, but it's
a reasonable compromise for now to say that a specific database like PCMIS is
going to be hosted on SQL Server, since PCMIS uses that
    SQL Server      SQLAlchemy
    SUBSTR          func.substr
    ASCII           

What about CaseNumber -- is that identifying? If not, it can remain the
internal key to identify cases. If it is, then we have to replace it.
The first character is 1,9,A-Z except Q, X, Y (n=25).
The second character is 0,A-Z except I, Q, U, X, Z (n=22).
So, pretty spread.
The digits seem to be approximately consecutive.
So it does look more like an internal PK than something identifiable.

Mind you, very often it is identical to CaseNumber. So, do we need a second
hash?

Our PCMIS copy certainly has free text (search the schema for text types).

===============================================================================
Therefore, views and the like 
===============================================================================

MAIN SOFTWARE CHANGES
- Support non-integer PIDs/MPIDs.
- Add an AlterMethod that is hash=hash_config_key_name
  with e.g.

    [hash_config_key_name]
    method = hmacsha256
    key = somesecretkey

TABLES
- If a table doesn't have a PK, give it an AUTONUMBER integer PK (e.g.
  "crate_pk"). That looks to be true of ?all tables.

VIEWS
- In general, not needed: we can use PatientId and CaseNumber as non-integer
  fields.
- We do need the geography views, though.

DATA DICTIONARY AUTOGENERATIO
- PatientId: always the PID.
- NHSNumber: always the MPID.
- CaseNumber: belongs in ddgen_extra_hash_fields, and users should give it the
  same hash key as for the PID-to-RID conversion, since it's often the same
  code.

"""


import argparse
import logging
from typing import Any

from sqlalchemy import (
    create_engine,
    MetaData,
)
from sqlalchemy.engine import Engine
from sqlalchemy.schema import Table

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
    get_column_names,
    set_print_not_execute,
)
from crate_anon.common.sqla import (
    get_pk_colnames,
    hack_in_mssql_xml_type,
    make_bigint_autoincrement_column,
)
from crate_anon.preprocess.rio_constants import (
    DEFAULT_GEOG_COLS,
    ONSPD_TABLE_POSTCODE,
)
from crate_anon.preprocess.rio_ddgen import DDHint

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

CRATE_COL_PK = "crate_pk"

CRATE_IDX_PK = "crate_idx_pk"  # for any patient table

CRATE_VIEW_SUFFIX = "_crateview"

PCMIS_COL_CASE_NUMBER = "CaseNumber"
PCMIS_COL_NHS_NUMBER = "NHSNumber"
PCMIS_COL_PATIENT_ID = "PatientId"
PCMIS_COL_POSTCODE = "PostCode"
PCMIS_COL_PREV_POSTCODE = "PreviousPostCode"

PCMIS_TABLE_CASE_CONTACT_DETAILS = "CaseContactDetails"
PCMIS_TABLE_MASTER_PATIENT = "PatientDetails"

VIEW_CASE_CONTACT_DETAILS_W_GEOG = PCMIS_TABLE_CASE_CONTACT_DETAILS + CRATE_VIEW_SUFFIX  # noqa
VIEW_PT_DETAIL_W_GEOG = PCMIS_TABLE_MASTER_PATIENT + CRATE_VIEW_SUFFIX


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
    # PCMIS core tables
    # -------------------------------------------------------------------------
    Case*.*
    Group*.*
    Lexicon*.*  # system lookup tables
    Lookups.*  # system lookup table
    lu*.*  # system lookup tables
    Patient*.*
    ReferralDetails.*
    System*.*  # system lookup tables
    Users.*  # staff
    # -------------------------------------------------------------------------
    # Custom views from CRATE
    # -------------------------------------------------------------------------

ddgen_allow_no_patient_info = False

ddgen_per_table_pid_field = {PCMIS_COL_PATIENT_ID}

ddgen_add_per_table_pids_to_scrubber = False

ddgen_master_pid_fieldname = {PCMIS_COL_NHS_NUMBER}

ddgen_table_blacklist = #
    # -------------------------------------------------------------------------
    # Blacklist: Prefixes: groups of tables; individual tables
    # -------------------------------------------------------------------------
    aspnet_*  # admin tables
    CaseCarer*  # details of carers
    CaseChild*  # details of children
    CaseEmergency*  # emergency contacts
    CaseEmployer*  # employer details
    MissingData  # system?
    ODBC_*  # admin tables
    PatientCarer*  # details of carers
    PatientDetails  # replaced by {VIEW_PT_DETAIL_W_GEOG}
    PatientChild*  # details of children
    PatientEmergency*  # emergency contacts
    PatientEmployer*  # employer details
    pcmis_*  # admin tables
    # -------------------------------------------------------------------------
    # Blacklist: CPFT custom
    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------
    # Blacklist: Views supersede
    # Below here, we have other tables suppressed because CRATE's views offer
    # more comprehensive alternatives
    # -------------------------------------------------------------------------
    {suppress_tables}

ddgen_table_whitelist =

ddgen_table_require_field_absolute = #
    # All tables/fields must have crate_pk
    {CRATE_COL_PK}

ddgen_table_require_field_conditional =
ddgen_field_blacklist =
ddgen_field_whitelist =
ddgen_pk_fields = {CRATE_COL_PK}
ddgen_constant_content = False
ddgen_constant_content_tables =
ddgen_nonconstant_content_tables =
ddgen_addition_only = False
ddgen_addition_only_tables =
ddgen_deletion_possible_tables =

ddgen_pid_defining_fieldnames = {VIEW_PT_DETAIL_W_GEOG}.{PCMIS_COL_PATIENT_ID}

ddgen_scrubsrc_patient_fields = # several of these:
    # ----------------------------------------------------------------------
    # Original PCMIS tables (some may be superseded by views; list both here;
    # if the table is blacklisted anyway, it doesn't matter).
    # ----------------------------------------------------------------------
    CaseContactDetails.CaseNumber
    CaseContactDetails.FirstName
    CaseContactDetails.MiddleName
    CaseContactDetails.LastName
    CaseContactDetails.DOB
    CaseContactDetails.Address*
    CaseContactDetails.TownCity
    CaseContactDetails.County
    CaseContactDetails.PostCode
    CaseContactDetails.TelHome
    CaseContactDetails.TelMobile
    CaseContactDetails.TelWork
    CaseContactDetails.FamilyName
    CaseContactDetails.PreviousName
    CaseContactDetails.PreviousAddress*
    CaseContactDetails.PreviousTownCity
    CaseContactDetails.PreviousCounty
    CaseContactDetails.PreviousPostCode
    CaseContactDetails.Email
    CaseContactDetails.OtherCaseNumber
    CaseContactDetails.NHSNumberVerified
    CaseEpisodes.LinkedCaseNumber
    PatientDetails.PatientID
    PatientDetails.FirstName
    PatientDetails.MiddleName
    PatientDetails.LastName
    PatientDetails.DOB
    PatientDetails.Address*  # Address1, Address2, Address3
    PatientDetails.TownCity
    PatientDetails.County
    PatientDetails.PostCode
    PatientDetails.Tel*  # TelHome, TelMobile, TelWork
    PatientDetails.NHSNumber
    PatientDetails.FamilyName
    PatientDetails.PreviousName
    PatientDetails.PreviousAddress*
    PatientDetails.PreviousTownCity
    PatientDetails.PreviousCounty
    PatientDetails.PreviousPostCode
    PatientDetails.Email
    PatientDetails.DependantChildren  # is VARCHAR(100)
    PatientDetails.LastNameAlias
    PatientDetails.FirstNameAlias
    PatientDetails.DisplayName
    # ----------------------------------------------------------------------
    # Views
    # ----------------------------------------------------------------------
    {VIEW_PT_DETAIL_W_GEOG}.PatientID
    {VIEW_PT_DETAIL_W_GEOG}.FirstName
    {VIEW_PT_DETAIL_W_GEOG}.MiddleName
    {VIEW_PT_DETAIL_W_GEOG}.LastName
    {VIEW_PT_DETAIL_W_GEOG}.DOB
    {VIEW_PT_DETAIL_W_GEOG}.Address*  # Address1, Address2, Address3
    {VIEW_PT_DETAIL_W_GEOG}.TownCity
    {VIEW_PT_DETAIL_W_GEOG}.County
    {VIEW_PT_DETAIL_W_GEOG}.PostCode
    {VIEW_PT_DETAIL_W_GEOG}.Tel*  # TelHome, TelMobile, TelWork
    {VIEW_PT_DETAIL_W_GEOG}.NHSNumber
    {VIEW_PT_DETAIL_W_GEOG}.FamilyName
    {VIEW_PT_DETAIL_W_GEOG}.PreviousName
    {VIEW_PT_DETAIL_W_GEOG}.PreviousAddress*
    {VIEW_PT_DETAIL_W_GEOG}.PreviousTownCity
    {VIEW_PT_DETAIL_W_GEOG}.PreviousCounty
    {VIEW_PT_DETAIL_W_GEOG}.PreviousPostCode
    {VIEW_PT_DETAIL_W_GEOG}.Email
    {VIEW_PT_DETAIL_W_GEOG}.DependantChildren  # is VARCHAR(100)
    {VIEW_PT_DETAIL_W_GEOG}.LastNameAlias
    {VIEW_PT_DETAIL_W_GEOG}.FirstNameAlias
    {VIEW_PT_DETAIL_W_GEOG}.DisplayName

ddgen_scrubsrc_thirdparty_fields = # several:
    # ----------------------------------------------------------------------
    # Original PCMIS tables (some may be superseded by views; list both here)
    # ----------------------------------------------------------------------
    CaseCarerDetails.CarerName
    CaseCarerDetails.CarerTelHome
    CaseCarerDetails.CarerTelWork
    CaseCarerDetails.CarerTelMobile
    CaseCarerDetails.CarerAddress*
    CaseCarerDetails.CarerTownCity
    CaseCarerDetails.CarerCounty
    CaseCarerDetails.CarerPostcode
    CaseChildDetails.ChildCarer  # NVARCHAR(50)
    CaseChildDetails.FirstName
    CaseChildDetails.MiddleName
    CaseChildDetails.LastName
    CaseChildDetails.DOB
    CaseEmergencyDetails.EmergencyContact
    CaseEmergencyDetails.EmergencyAddress*
    CaseEmergencyDetails.EmergencyTownCity
    CaseEmergencyDetails.EmergencyCounty
    CaseEmergencyDetails.EmergencyPostcode
    CaseEmergencyDetails.EmergencyTelephone
    CaseEmployerDetails.EmployerName
    CaseEmployerDetails.EmployerJobTitle
    CaseEmployerDetails.EmployerContact
    CaseEmployerDetails.EmployerAddress*
    CaseEmployerDetails.EmployerTownCity
    CaseEmployerDetails.EmployerCounty
    CaseEmployerDetails.EmployerPostcode
    CaseEmployerDetails.EmployerTelephone
    PatientCarerDetails.CarerName
    PatientCarerDetails.CarerTelHome
    PatientCarerDetails.CarerTelWork
    PatientCarerDetails.CarerTelMobile
    PatientCarerDetails.CarerAddress*
    PatientCarerDetails.CarerTownCity
    PatientCarerDetails.CarerCounty
    PatientCarerDetails.CarerPostCode
    PatientChildDetails.ChildCarer  # VARCHAR(50)
    PatientChildDetails.FirstName
    PatientChildDetails.MiddleName
    PatientChildDetails.LastName
    PatientChildDetails.DOB
    PatientEmergencyDetails.NextOfKin
    PatientEmergencyDetails.EmergencyContact
    PatientEmergencyDetails.EmergencyAddress*
    PatientEmergencyDetails.EmergencyTownCity
    PatientEmergencyDetails.EmergencyCounty
    PatientEmergencyDetails.EmergencyPostcode
    PatientEmergencyDetails.EmergencyTelephone
    PatientEmployerDetails.EmployerName
    PatientEmployerDetails.EmployerJobTitle
    PatientEmployerDetails.EmployerContact
    PatientEmployerDetails.EmployerAddress*
    PatientEmployerDetails.EmployerTownCity
    PatientEmployerDetails.EmployerCounty
    PatientEmployerDetails.EmployerPostcode
    PatientEmployerDetails.EmployerTelephone
    # ----------------------------------------------------------------------
    # CRATE views
    # ----------------------------------------------------------------------

ddgen_scrubsrc_thirdparty_xref_pid_fields = # several:
    # ----------------------------------------------------------------------
    # Original PCMIS tables (some may be superseded by views; list both here)
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # RCEP/CRATE views
    # ----------------------------------------------------------------------

ddgen_required_scrubsrc_fields = # several:
    PatientDetails.FirstName
    PatientDetails.LastName  # always present, but FamilyName can be NULL
    PatientDetails.DOB

ddgen_scrubmethod_code_fields = # variants:
    *PostCode
    *Postcode

ddgen_scrubmethod_date_fields =
    *DOB*

ddgen_scrubmethod_number_fields = #
    *Tel*
    *NHSNumber*

ddgen_scrubmethod_phrase_fields = *Address*

ddgen_safe_fields_exempt_from_scrubbing =

    # PCMIS mostly uses string column lengths of 1, 20, 32, 50, 64, 100, 128,
    # 200, 250, 255, 256, 500, 1000, 2000, 4000, unlimited.
    # So what length is the minimum for "free text"?
    # - 20: mostly postcodes, lookup codes
    # - 32: telephone numbers
    # - 50: includes CaseAssessmentContactType.Purpose, plus lookup codes.
    #       Also includes CaseChildDetails.Impact
    # - 64: mostly codes; also e.g. ReferralDetails.EndOfCareReason
    # - 100: lots of generic things, like CaseAssessmentCustom1.Q1
ddgen_min_length_for_scrubbing = 50

ddgen_truncate_date_fields =
    CaseContactDetails.DOB
    PatientDetails.DOB

ddgen_filename_to_text_fields =
ddgen_binary_to_text_field_pairs =
ddgen_skip_row_if_extract_text_fails_fields =
ddgen_rename_tables_remove_suffixes = {CRATE_VIEW_SUFFIX}
ddgen_patient_opt_out_fields =

ddgen_extra_hash_fields = CaseNumber, pcmis_case_number_hashdef

    # YOU WILL NEED TO DO THIS:
    # (1) add "pcmis_case_number_hashdef" to your "extra_hash_config_sections"
    #     setting;
    # (2) add a "pcmis_case_number_hashdef" section, like this:
    #       [pcmis_case_number_hashdef]
    #       hash_method = HMAC_MD5
    #       secret_key = my_special_secret_phrase_123
    # and obviously you should use your own secret phrase, not this one!

ddgen_index_fields =
ddgen_allow_fulltext_indexing = True

ddgen_force_lower_case = False
ddgen_convert_odd_chars_to_underscore = True

    """.format(  # noqa
        CRATE_COL_PK=CRATE_COL_PK,
        CRATE_VIEW_SUFFIX=CRATE_VIEW_SUFFIX,
        PCMIS_COL_NHS_NUMBER=PCMIS_COL_NHS_NUMBER,
        PCMIS_COL_PATIENT_ID=PCMIS_COL_PATIENT_ID,
        PCMIS_TABLE_MASTER_PATIENT=PCMIS_TABLE_MASTER_PATIENT,
        suppress_tables="\n    ".join(ddhint.get_suppressed_tables()),
        VIEW_PT_DETAIL_W_GEOG=VIEW_PT_DETAIL_W_GEOG,
    )


# =============================================================================
# Geography views
# =============================================================================

def add_geography_view(basetable: str,
                       viewname: str,
                       engine: Engine,
                       progargs: Any,
                       ddhint: DDHint) -> None:  # ddhint modified
    postcode_alias_1 = "_postcodetable1"
    postcode_alias_2 = "_postcodetable2"
    prev_prefix = "previous_"

    # Re-read column names, as we may have inserted some recently by hand that
    # may not be in the initial metadata.
    orig_column_names = get_column_names(engine, tablename=basetable, 
                                         sort=True)

    # Remove any original column names being overridden by new ones.
    # (Could also do this the other way around!)
    newcols_lowercase = (
        [x.lower() for x in progargs.geogcols] +
        [prev_prefix + x.lower() for x in progargs.geogcols]
    )
    orig_column_names = [x for x in orig_column_names
                         if x.lower() not in newcols_lowercase]
    orig_column_specs = [
        "{t}.{c}".format(t=basetable, c=col)
        for col in orig_column_names
    ]
    geog_col_specs = [
        "{postcode_alias_1}.{c} AS {c}".format(
            postcode_alias_1=postcode_alias_1,
            c=col)
        for col in sorted(progargs.geogcols, key=lambda x: x.lower())
    ] + [
        "{postcode_alias_2}.{c} AS {prev_prefix}{c}".format(
            postcode_alias_2=postcode_alias_2,
            prev_prefix=prev_prefix,
            c=col)
        for col in sorted(progargs.geogcols, key=lambda x: x.lower())
    ]

    ensure_columns_present(engine,
                           tablename=basetable,
                           column_names=[PCMIS_COL_POSTCODE,
                                         PCMIS_COL_PREV_POSTCODE])
    select_sql = """
        SELECT {origcols},
            {geogcols}
        FROM {basetable}
        -- PCMIS can have either 'XX99 9XX' or 'XX999XX' format:
        LEFT JOIN {pdb}.{pcdtab} AS {postcode_alias_1}
            ON REPLACE({basetable}.{PCMIS_COL_POSTCODE},
                       ' ',
                       '') = {postcode_alias_1}.pcd_nospace
        LEFT JOIN {pdb}.{pcdtab} AS {postcode_alias_2}
            ON REPLACE({basetable}.{PCMIS_COL_PREV_POSTCODE},
                       ' ',
                       '') = {postcode_alias_2}.pcd_nospace
    """.format(
        basetable=basetable,
        origcols=",\n            ".join(orig_column_specs),
        geogcols=",\n            ".join(geog_col_specs),
        pdb=progargs.postcodedb,
        pcdtab=ONSPD_TABLE_POSTCODE,
        PCMIS_COL_POSTCODE=PCMIS_COL_POSTCODE,
        PCMIS_COL_PREV_POSTCODE=PCMIS_COL_PREV_POSTCODE,
        postcode_alias_1=postcode_alias_1,
        postcode_alias_2=postcode_alias_2,
    )
    create_view(engine, viewname, select_sql)
    assert_view_has_same_num_rows(engine, basetable, viewname)
    ddhint.suppress_table(basetable)


def add_geography_views(engine: Engine,
                        progargs: Any,
                        ddhint: DDHint) -> None:  # ddhint modified
    add_geography_view(PCMIS_TABLE_MASTER_PATIENT,
                       VIEW_PT_DETAIL_W_GEOG,
                       engine, progargs, ddhint)
    add_geography_view(PCMIS_TABLE_CASE_CONTACT_DETAILS,
                       VIEW_CASE_CONTACT_DETAILS_W_GEOG,
                       engine, progargs, ddhint)


def drop_geography_views(engine: Engine) -> None:
    drop_view(engine, VIEW_PT_DETAIL_W_GEOG)
    drop_view(engine, VIEW_CASE_CONTACT_DETAILS_W_GEOG)


# =============================================================================
# Generic table processors
# =============================================================================

def process_table(table: Table, engine: Engine, progargs: Any) -> None:
    tablename = table.name
    column_names = table.columns.keys()
    log.debug("TABLE: {}; COLUMNS: {}".format(tablename, column_names))

    existing_pk_cols = get_pk_colnames(table)
    adding_crate_pk = not existing_pk_cols

    required_cols = [CRATE_COL_PK] if not progargs.print else []

    if progargs.drop_danger_drop:
        # ---------------------------------------------------------------------
        # DROP STUFF! Opposite order to creation (below)
        # ---------------------------------------------------------------------
        drop_indexes(engine, table, [CRATE_IDX_PK])
        drop_columns(engine, table, [CRATE_COL_PK])
    else:
        # ---------------------------------------------------------------------
        # CREATE STUFF!
        # ---------------------------------------------------------------------
        # SQL Server requires Table-bound columns in order to generate DDL:
        if adding_crate_pk:
            crate_pk_col = make_bigint_autoincrement_column(CRATE_COL_PK,
                                                            engine.dialect)
            table.append_column(crate_pk_col)
            add_columns(engine, table, [crate_pk_col])
        ensure_columns_present(engine, tablename=table.name,
                               column_names=required_cols)
        add_indexes(engine, table, [{'index_name': CRATE_IDX_PK,
                                     'column': CRATE_COL_PK,
                                     'unique': True}])


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
        drop_geography_views(engine)
        if not progargs.debug_skiptables:
            process_all_tables(engine, metadata, progargs)
    else:
        # Tables first, then views
        if not progargs.debug_skiptables:
            process_all_tables(engine, metadata, progargs)
        if progargs.postcodedb:
            add_geography_views(engine, progargs, ddhint)

    if progargs.settings_filename:
        with open(progargs.settings_filename, 'w') as f:
            print(get_pcmis_dd_settings(ddhint), file=f)


if __name__ == '__main__':
    pdb_run(main)


# *** When this is done, find out why the anonymiser is using so much memory.
# https://www.huyng.com/posts/python-performance-analysis
# http://chase-seibert.github.io/blog/2013/08/03/diagnosing-memory-leaks-python.html  # noqa
