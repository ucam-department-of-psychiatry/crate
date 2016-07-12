#!/usr/bin/env python
# crate_anon/tools/preprocess_rio.py

import argparse
import logging
import sys

from sqlalchemy import (
    create_engine,
    inspect,
    MetaData,
)

from crate_anon.anonymise.constants import MYSQL_CHARSET
from crate_anon.anonymise.logsupport import configure_logger_for_colour

log = logging.getLogger(__name__)
metadata = MetaData()


# =============================================================================
# Constants
# =============================================================================

AUTONUMBER_COLTYPE = "INTEGER IDENTITY(1, 1) NOT NULL"

# Tables in RiO v6.2 Core:
RIO_TABLE_MASTER_PATIENT = "ClientIndex"
RIO_TABLE_ADDRESS = "ClientAddress"
RIO_TABLE_PROGRESS_NOTES = "PrgProgressNote"
# Columns in RiO Core:
RIO_COL_PATIENT_ID = "ClientID"  # RiO 6.2: VARCHAR(15)
RIO_COL_NHS_NUMBER = "NNN"  # RiO 6.2: CHAR(10) ("National NHS Number")
RIO_COL_POSTCODE = "PostCode"  # ClientAddress.PostCode
RIO_COL_DEFAULT_PK = "SequenceID"  # INT
RIO_COL_USER_ASSESS_DEFAULT_PK = "type12_NoteID"

# Tables in RiO CRIS Extract Program (RCEP) output database:
RCEP_TABLE_MASTER_PATIENT = "Client_Demographic_Details"
RCEP_TABLE_ADDRESS = "Client_Address_History"
RCEP_TABLE_PROGRESS_NOTES = "Progress_Notes"
# Columns in RCEP extract:
RCEP_COL_PATIENT_ID = "Client_ID"  # RCEP: VARCHAR(15)
RCEP_COL_NHS_NUMBER = "NHS_Number"  # RCEP: CHAR(10)
RCEP_COL_POSTCODE = "Post_Code"  # RCEP: NVARCHAR(10)
# ... general format (empirically): "XX12 3YY" or "XX1 3YY"; "ZZ99" for unknown
# This matches the ONPD "pdcs" format.
RCEP_COL_MANGLED_KEY = "Document_ID"
# In RCEP, Document_ID is VARCHAR(MAX), and is often:
#   'global_table_id_9_or_10_digits' + '_' + 'pk_int_as_string'
# HOWEVER, the last part is not always unique; e.g. Care_Plan_Interventions.
# - Care_Plan_Interventions has massive tranches of ENTIRELY identical rows,
#   including a column called, ironically, "Unique_Key".
# - Therefore, we could either ditch the key entirely, or just use a non-UNIQUE
#   index (and call it "key" not "pk").
# AND THEN... In Client_Family, we have Document_ID values like
#   773577794_1000000_1000001
#   ^^^^^^^^^ ^^^^^^^ ^^^^^^^
#   table ID  RiO#    Family member's RiO#
#
#   ... there is no unique ID. And we don't need the middle part as we already
#   have Client_ID. So this is not very useful. We could mangle out the second
#   and subsequent '_' characters to give a unique number here, which would
#   meaning having PK as BIGINT not INTEGER.
# - SQL Server's ROW_NUMBER() relates to result sets.
# - However, ADD pkname INT IDENTITY(1, 1) works beautifully and
#   autopopulates existing tables.

# CPFT hacks (RiO tables added to RCEP output):
CPFT_RCEP_TABLE_FULL_PROGRESS_NOTES = "Progress_Notes_II"

# Columns in ONS Postcode Database (from CRATE import):
ONSPD_TABLE_POSTCODE = "postcode"
DEFAULT_GEOG_COLS = [
    "pcon", "pct", "nuts", "lea", "statsward", "casward",
    "lsoa01", "msoa01", "ur01ind", "oac01", "lsoa11",
    "msoa11", "parish", "bua11", "buasd11", "ru11ind",
    "oac11", "imd",
]

# Columns added:
CRATE_COL_PK = "crate_pk"
# Do NOT use 'id'; this appears in RiO ClientAlternativeId /
# RCEP Client_Alternative_ID. "pk" is OK for RCEP + RiO, but clarity is good
CRATE_COL_RIO_NUMBER = "crate_rio_number"
# "rio_number" is OK for RCEP + RiO, but clarity is good
CRATE_COL_NHS_NUMBER = "crate_nhs_number_int"
# "nhs_number_int" is OK for RCEP + RiO, but again...
# For RCEP, in SQL Server, check existing columns with:
#   USE database;
#   SELECT column_name, table_name
#       FROM information_schema.columns
#       WHERE column_name = 'something';
# For RiO, for now, check against documented table structure.

# For progress notes:
CRATE_COL_MAX_SUBNUM = "crate_max_subnum_for_notenum"
CRATE_COL_LAST_NOTE = "crate_last_note_in_edit_chain"

# Indexes added:
CRATE_IDX_PK = "crate_idx_pk"  # for any patient table
CRATE_IDX_RIONUM = "crate_idx_rionum"  # for any patient table
CRATE_IDX_RIONUM_NOTENUM = "crate_idx_rionum_notenum"  # for Progress Notes
CRATE_IDX_MAX_SUBNUM = "crate_idx_max_subnum"
CRATE_IDX_LAST_NOTE = "crate_idx_last_note"

# Views added:
VIEW_PROGRESS_NOTES_CURRENT = "progress_notes_current_crate"
VIEW_ADDRESS_WITH_GEOGRAPHY = "client_address_with_geography_crate"

RIO_6_2_ATYPICAL_PKS = {
    # These are table: pk_field mappings for PATIENT tables, i.e. those
    # containing the ClientID field, where that PK is not the default of
    # SequenceID.

    # -------------------------------------------------------------------------
    # RiO Core
    # -------------------------------------------------------------------------

    # Ams*: Appointment Management System
    'AmsAppointmentContactActivity': 'ActivitySequenceID',
    'AmsAppointmentOtherHCP': None,  # non-patient; non-unique SequenceID
    # ... SequenceID is non-unique and the docs also list it as an FK;
    #     ActivitySequenceID this is unique and a PK
    'AmsReferralDatesArchive': 'AMSSequenceID',
    # ... UNVERIFIED as no rows in our data; listed as a PK and an FK
    'AmsReferralListUrgency': None,
    'AmsReferralListWaitingStatus': None,

    'CarePlanIndex': 'CarePlanID',
    'CarePlanProblemOrder': None,

    'ClientAddressMerged': None,  # disused table
    'ClientCareSpell': None,  # CareSpellNum is usually 1 for a given ClientID
    'ClientDocumentAdditionalClient': None,
    'ClientFamily': None,
    'ClientFamilyLink': None,
    'ClientGPMerged': None,
    'ClientHealthCareProvider': None,
    'ClientMerge': None,
    'ClientMerged': None,
    'ClientName': 'ClientNameID',
    'ClientOtherDetail': None,  # not in docs, but looks like Core
    'ClientPhoto': None,
    'ClientPhotoMerged': None,
    'ClientProperty': None,
    'ClientPropertyMerged': None,
    'ClientTelecom': 'ClientTelecomID',
    'ClientUpdatePDSCache': None,

    # Con*: Contracts
    'Contract': 'ContractNumber',
    'ConAdHocAwaitingApproval': 'SequenceNo',
    'ConClientInitialBedRate': None,
    'ConClinicHistory': 'SequenceNo',
    'ConLeaveDiscountHistory': 'SequenceNo',

    # Not documented, but looks like Core
    'Deceased': None,  # or possibly TrustWideID (or just ClientID!)

    'DemClientDeletedDetails': None,

    # EP: E-Prescribing
    # ... with DA: Drug Administration
    # ... with DS: Drug Service
    'EPClientConditions': 'RowID',
    'EPClientPrescription': 'PrescriptionID',
    'EPClientSensitivities': None,  # UNVERIFIED: None? Joint PK on ProdID?
    'EPDiscretionaryDrugClientLink': None,
    'EPVariableDosageDrugLink': 'HistoryID',  # UNVERIFIED
    'EPClientAllergies': 'ReactionID',
    'DAConcurrencyControl': None,
    'DAIPPrescription': 'PrescriptionID',
    'DSBatchPatientGroups': None,
    'DSMedicationBatchContinue': None,
    'DSMedicationBatchLink': None,

    # Ims*: Inpatient Management System
    'ImsEventLeave': 'UniqueSequenceID',  # SequenceID
    'ImsEventMovement': None,
    'ImsEventRefno': None,  # Not in docs but looks like Core.
    'ImsEventRefnoBAKUP': None,  # [Sic.] Not in docs but looks like Core.

    # LR*: Legitimate Relationships
    'LRIdentifiedCache': None,

    # Mes*: messaging
    'MesLettersGenerated': 'Reference',

    # Mnt*: Mental Health module (re MHA detention)
    'MntArtAttendee': None,  # SequenceID being "of person within a meeting"
    'MntArtOutcome': None,  # ditto
    'MntArtPanel': None,  # ditto
    'MntArtRpts': None,  # ditto
    'MntArtRptsReceived': None,  # ditto
    'MntClientEctSection62': None,
    'MntClientMedSection62': None,
    'MntClientSectionDetailCareCoOrdinator': None,
    'MntClientSectionDetailCourtAppearance': None,
    'MntClientSectionDetailFMR': None,
    'MntClientSectionReview': None,

    # NDTMS*: Nation(al?) Drug Treatment Monitoring System

    # SNOMED*: SNOMED
    'SNOMED_Client': 'SC_ID',

    # UserAssess*: user assessment (= non-core?) tables.
    # See other default PK below: type12:

    # -------------------------------------------------------------------------
    # Non-core? No docs available.
    # -------------------------------------------------------------------------
    # Chd*: presumably, child development
    'ChdClientDevCheckBreastFeeding': None,
    # ... guess; DevChkSeqID is probably FK to ChdClientDevCheck.SequenceID

    # ??? But it has q1-q30, qu2-14, home, sch, comm... assessment tool...
    'CYPcurrentviewImport': None,  # not TrustWideID (which is non-unique)

    'GoldmineIfcMapping': None,  # no idea, really, and no data to explore

    'KP90ErrorLog': None,

    'ReportsOutpatientWaitersHashNotSeenReferrals': None,
    'ReportsOutpatientWaitersNotSeenReferrals': None,
}

RIO_6_2_ATYPICAL_PATIENT_ID_COLS = {
    'SNOMED_Client': 'SC_ClientID',
}


# =============================================================================
# Ancillary functions
# =============================================================================

def die(msg):
    log.critical(msg)
    sys.exit(1)


def format_sql_for_print(sql):
    # Remove blank lines and trailing spaces
    lines = list(filter(None, [x.replace("\t", "    ").rstrip()
                               for x in sql.splitlines()]))
    # Shift all lines left if they're left-padded
    firstleftpos = float('inf')
    for line in lines:
        leftpos = len(line) - len(line.lstrip())
        firstleftpos = min(firstleftpos, leftpos)
    if firstleftpos > 0:
        lines = [x[firstleftpos:] for x in lines]
    return "\n".join(lines)


def sql_fragment_cast_to_int(expr):
    # Conversion to INT:
    # http://stackoverflow.com/questions/2000045
    # http://stackoverflow.com/questions/14719760  # this one
    # http://stackoverflow.com/questions/14692131
    return "CASE WHEN {expr} NOT LIKE '%[^0-9]%' " \
           "THEN CAST({expr} AS INTEGER) ELSE NULL END".format(expr=expr)


def execute(engine, args, sql):
    log.debug(sql)
    if args.print:
        print(format_sql_for_print(sql) + "\n;")
        # extra \n in case the SQL ends in a comment
    else:
        engine.execute(sql)


def add_columns(engine, args, table, name_coltype_dict):
    existing_column_names = get_column_names(engine, table=table,
                                             to_lower=True)
    column_defs = []
    for name, coltype in name_coltype_dict.items():
        if name.lower() not in existing_column_names:
            column_defs.append("{} {}".format(name, coltype))
        else:
            log.debug("Table '{}': column '{}' already exists; not "
                      "adding".format(table.name, name))
    # ANSI SQL: add one column at a time: ALTER TABLE ADD [COLUMN] coldef
    #   - i.e. "COLUMN" optional, one at a time, no parentheses
    #   - http://www.contrib.andrew.cmu.edu/~shadow/sql/sql1992.txt
    # MySQL: ALTER TABLE ADD [COLUMN] (a INT, b VARCHAR(32));
    #   - i.e. "COLUMN" optional, parentheses required for >1, multiple OK
    #   - http://dev.mysql.com/doc/refman/5.7/en/alter-table.html
    # MS SQL Server: ALTER TABLE ADD COLUMN a INT, B VARCHAR(32);
    #   - i.e. no "COLUMN", no parentheses, multiple OK
    #   - https://msdn.microsoft.com/en-us/library/ms190238.aspx
    #   - https://msdn.microsoft.com/en-us/library/ms190273.aspx
    #   - http://stackoverflow.com/questions/2523676/alter-table-add-multiple-columns-ms-sql  # noqa
    # SQLAlchemy doesn't provide a shortcut for this.
    for column_def in column_defs:
        log.info("Table '{}': adding column {}".format(
            table.name, column_def))
        execute(engine, args, """
            ALTER TABLE {tablename} ADD {column_def}
        """.format(tablename=table.name, column_def=column_def))


def drop_columns(engine, args, table, column_names):
    existing_column_names = get_column_names(engine, table=table,
                                             to_lower=True)
    for name in column_names:
        if name.lower() not in existing_column_names:
            log.debug("Table '{}': column '{}' does not exist; not "
                      "dropping".format(table.name, name))
        else:
            log.info("Table '{}': dropping column '{}'".format(table.name,
                                                               name))
            sql = "ALTER TABLE {t} DROP COLUMN {c}".format(t=table.name,
                                                           c=name)
            # SQL Server: http://www.techonthenet.com/sql_server/tables/alter_table.php  # noqa
            # MySQL: http://dev.mysql.com/doc/refman/5.7/en/alter-table.html
            execute(engine, args, sql)


def add_indexes(engine, args, table, indexdictlist):
    existing_index_names = get_index_names(engine, table=table, to_lower=True)
    for idxdefdict in indexdictlist:
        index_name = idxdefdict['index_name']
        column = idxdefdict['column']
        unique = idxdefdict.get('unique', False)
        if index_name.lower() not in existing_index_names:
            log.info("Table '{}': adding index '{}' on columns '{}'".format(
                table.name, index_name, column))
            execute(engine, args, """
              CREATE{unique} INDEX {idxname} ON {tablename} ({column})
            """.format(
                unique=" UNIQUE" if unique else "",
                idxname=index_name,
                tablename=table.name,
                column=column,
            ))
        else:
            log.debug("Table '{}': index '{}' already exists; not "
                      "adding".format(table.name, index_name))


def drop_indexes(engine, args, table, index_names):
    existing_index_names = get_index_names(engine, table=table, to_lower=True)
    for index_name in index_names:
        if index_name.lower() not in existing_index_names:
            log.debug("Table '{}': index '{}' does not exist; not "
                      "dropping".format(table.name, index_name))
        else:
            log.info("Table '{}': dropping index '{}'".format(table.name,
                                                              index_name))
            if engine.dialect.name == 'mysql':
                sql = "ALTER TABLE {t} DROP INDEX {i}".format(t=table.name,
                                                              i=index_name)
            elif engine.dialect.name == 'mssql':
                sql = "DROP INDEX {t}.{i}".format(t=table.name, i=index_name)
            else:
                assert False, "Unknown dialect: {}".format(engine.dialect.name)
            execute(engine, args, sql)


def get_view_names(engine, to_lower=False, sort=False):
    inspector = inspect(engine)
    view_names = inspector.get_view_names()
    if to_lower:
        view_names = [x.lower() for x in view_names]
    if sort:
        view_names = sorted(view_names, key=lambda x: x.lower())
    return view_names


def get_column_names(engine, tablename=None, table=None, to_lower=False,
                     sort=False):
    """
    Reads columns names afresh from the database (in case metadata is out of
    date.
    """
    assert (table is not None) != bool(tablename), "Need table XOR tablename"
    tablename = tablename or table.name
    inspector = inspect(engine)
    columns = inspector.get_columns(tablename)
    column_names = [x['name'] for x in columns]
    if to_lower:
        column_names = [x.lower() for x in column_names]
    if sort:
        column_names = sorted(column_names, key=lambda x: x.lower())
    return column_names


def get_index_names(engine, tablename=None, table=None, to_lower=False):
    """
    Reads index names from the database.
    """
    # http://docs.sqlalchemy.org/en/latest/core/reflection.html
    assert (table is not None) != bool(tablename), "Need table XOR tablename"
    tablename = tablename or table.name
    inspector = inspect(engine)
    indexes = inspector.get_indexes(tablename)
    index_names = [x['name'] for x in indexes if x['name']]
    # ... at least for SQL Server, there always seems to be a blank one
    # with {'name': None, ...}.
    if to_lower:
        index_names = [x.lower() for x in index_names]
    return index_names


def ensure_columns_present(engine, table=None, tablename=None,
                           column_names=None):
    assert column_names, "Need column_names"
    assert (table is not None) != bool(tablename), "Need table XOR tablename"
    tablename = tablename or table.name
    existing_column_names = get_column_names(engine, tablename=tablename,
                                             to_lower=True)
    for col in column_names:
        if col.lower() not in existing_column_names:
            die("Column '{}' missing from table '{}'".format(col, tablename))


def create_view(engine, args, viewname, select_sql):
    # MySQL has CREATE OR REPLACE VIEW.
    # SQL Server doesn't: http://stackoverflow.com/questions/18534919
    if engine.dialect.name == 'mysql':
        sql = "CREATE OR REPLACE VIEW {viewname} AS {select_sql}".format(
            viewname=viewname,
            select_sql=select_sql,
        )
    else:
        drop_view(engine, args, viewname)
        sql = "CREATE VIEW {viewname} AS {select_sql}".format(
            viewname=viewname,
            select_sql=select_sql,
        )
    log.info("Creating view: '{}'".format(viewname))
    execute(engine, args, sql)


def drop_view(engine, args, viewname):
    # MySQL has DROP VIEW IF EXISTS, but SQL Server only has that from
    # SQL Server 2016 onwards.
    # - https://msdn.microsoft.com/en-us/library/ms173492.aspx
    # - http://dev.mysql.com/doc/refman/5.7/en/drop-view.html
    view_names = get_view_names(engine, to_lower=True)
    if viewname.lower() not in view_names:
        log.debug("View {} does not exist; not dropping".format(viewname))
    else:
        sql = "DROP VIEW {viewname}".format(viewname=viewname)
        execute(engine, args, sql)


# =============================================================================
# Generic table processors
# =============================================================================

def table_is_rio_type(tablename, args):
    if args.rio:
        return True
    if not args.cpft:
        return False
    # RCEP + CPFT modifications: there's one RiO table in the mix
    return tablename == args.full_prognotes_table


def get_rio_pk_col_patient_table(table):
    if table.name.startswith('UserAssess'):
        default = RIO_COL_USER_ASSESS_DEFAULT_PK
    else:
        default = RIO_COL_DEFAULT_PK
    pkcol = RIO_6_2_ATYPICAL_PKS.get(table.name, default)
    # log.debug("get_rio_pk_col: {} -> {}".format(table.name, pkcol))
    return pkcol


def get_rio_patient_id_col(table):
    patient_id_col = RIO_6_2_ATYPICAL_PATIENT_ID_COLS.get(table.name,
                                                          RIO_COL_PATIENT_ID)
    # log.debug("get_rio_patient_id_col: {} -> {}".format(table.name,
    #                                                     patient_id_col))
    return patient_id_col


def get_rio_pk_col_nonpatient_table(table):
    if RIO_COL_DEFAULT_PK in table.columns.keys():
        default = RIO_COL_DEFAULT_PK
    else:
        default = None
    return RIO_6_2_ATYPICAL_PKS.get(table.name, default)


def process_patient_table(table, engine, args):
    log.info("Patient table: '{}'".format(table.name))
    rio_type = table_is_rio_type(table.name, args)
    if rio_type:
        rio_pk = get_rio_pk_col_patient_table(table)
        string_pt_id = get_rio_patient_id_col(table)
        required_cols = [string_pt_id]
    else:  # RCEP type
        rio_pk = None
        required_cols = [RCEP_COL_PATIENT_ID]
        string_pt_id = RCEP_COL_PATIENT_ID
    if not args.print:
        required_cols.extend([CRATE_COL_PK, CRATE_COL_RIO_NUMBER])
    # -------------------------------------------------------------------------
    # Add pk and rio_number columns, if not present
    # -------------------------------------------------------------------------
    if rio_type and rio_pk is not None:
        crate_pk_type = 'INTEGER'  # can't do NOT NULL; need to populate it
        required_cols.append(rio_pk)
    else:  # RCEP type, or no PK in RiO
        crate_pk_type = AUTONUMBER_COLTYPE  # autopopulates
    add_columns(engine, args, table, {
        CRATE_COL_PK: crate_pk_type,
        CRATE_COL_RIO_NUMBER: 'INTEGER',
    })

    # -------------------------------------------------------------------------
    # Update pk and rio_number values, if not NULL
    # -------------------------------------------------------------------------
    ensure_columns_present(engine, table=table, column_names=required_cols)
    log.info("Table '{}': updating columns '{}' and '{}'".format(
        table.name, CRATE_COL_PK, CRATE_COL_RIO_NUMBER))
    cast_id_to_int = sql_fragment_cast_to_int(string_pt_id)
    if rio_type and rio_pk:
        execute(engine, args, """
            UPDATE {tablename} SET
                {crate_pk} = {rio_pk},
                {crate_rio_number} = {cast_id_to_int}
            WHERE
                {crate_pk} IS NULL
                OR {crate_rio_number} IS NULL
        """.format(
            tablename=table.name,
            crate_pk=CRATE_COL_PK,
            rio_pk=rio_pk,
            crate_rio_number=CRATE_COL_RIO_NUMBER,
            cast_id_to_int=cast_id_to_int,
        ))
    else:
        # RCEP format, or RiO with no PK
        # crate_pk is autogenerated as an INT IDENTITY field
        execute(engine, args, """
            UPDATE {tablename} SET
                {crate_rio_number} = {cast_id_to_int}
            WHERE
                {crate_rio_number} IS NULL
        """.format(  # noqa
            tablename=table.name,
            crate_rio_number=CRATE_COL_RIO_NUMBER,
            cast_id_to_int=cast_id_to_int,
        ))
    """
    Chucked:
        ensure_columns_present(... RCEP_COL_MANGLED_KEY...)

        {pk} = CAST(
            SUBSTRING(
                {rcep_mangled_pk},
                CHARINDEX('_', {rcep_mangled_pk}) + 1,
                LEN({rcep_mangled_pk}) - CHARINDEX('_', {rcep_mangled_pk})
            ) AS INTEGER
        ),

        # pk=CRATE_COL_PK,
        # rcep_mangled_pk=RCEP_COL_MANGLED_KEY,
    """
    # -------------------------------------------------------------------------
    # Add indexes, if absent
    # -------------------------------------------------------------------------
    # Note that the indexes are unlikely to speed up the WHERE NOT NULL search
    # above, so it doesn't matter that we add these last. Their use is for
    # the subsequent CRATE anonymisation table scans.
    add_indexes(engine, args, table, [
        {
            'index_name': CRATE_IDX_PK,
            'column': CRATE_COL_PK,
            'unique': True,
        },
        {
            'index_name': CRATE_IDX_RIONUM,
            'column': CRATE_COL_RIO_NUMBER,
        },
    ])


def drop_for_patient_table(table, engine, args):
    drop_indexes(engine, args, table, [CRATE_IDX_PK, CRATE_IDX_RIONUM])
    drop_columns(engine, args, table, [CRATE_COL_PK, CRATE_COL_RIO_NUMBER])


def process_nonpatient_table(table, engine, args):
    if args.rcep:
        return
    pk_col = get_rio_pk_col_nonpatient_table(table)
    if pk_col:
        add_columns(engine, args, table, {CRATE_COL_PK: 'INTEGER'})
    else:
        add_columns(engine, args, table, {CRATE_COL_PK: AUTONUMBER_COLTYPE})
    if not args.print:
        ensure_columns_present(engine, table=table,
                               column_names=[CRATE_COL_PK])
    if pk_col:
        execute(engine, args, """
            UPDATE {tablename} SET {crate_pk} = {rio_pk}
            WHERE {crate_pk} IS NULL
        """.format(tablename=table.name,
                   crate_pk=CRATE_COL_PK,
                   rio_pk=pk_col))
    add_indexes(engine, args, table, [{'index_name': CRATE_IDX_PK,
                                       'column': CRATE_COL_PK,
                                       'unique': True}])


def drop_for_nonpatient_table(table, engine, args):
    drop_indexes(engine, args, table, [CRATE_IDX_PK])
    drop_columns(engine, args, table, [CRATE_COL_PK])


# =============================================================================
# Specific table processors
# =============================================================================

def process_master_patient_table(table, engine, args):
    add_columns(engine, args, table, {
        CRATE_COL_NHS_NUMBER: 'BIGINT',
    })
    if args.rcep:
        nhscol = RCEP_COL_NHS_NUMBER
    else:
        nhscol = RIO_COL_NHS_NUMBER
    log.info("Table '{}': updating column '{}'".format(table.name, nhscol))
    ensure_columns_present(engine, table=table, column_names=[nhscol])
    if not args.print:
        ensure_columns_present(engine, table=table, column_names=[
            CRATE_COL_NHS_NUMBER])
    execute(engine, args, """
        UPDATE {tablename} SET
            {nhs_number_int} = CAST({nhscol} AS BIGINT)
            WHERE {nhs_number_int} IS NULL
    """.format(
        tablename=table.name,
        nhs_number_int=CRATE_COL_NHS_NUMBER,
        nhscol=nhscol,
    ))


def drop_for_master_patient_table(table, engine, args):
    drop_columns(engine, args, table, [CRATE_COL_NHS_NUMBER])


def process_progress_notes(table, engine, args):
    add_columns(engine, args, table, {
        CRATE_COL_MAX_SUBNUM: 'INTEGER',
        CRATE_COL_LAST_NOTE: 'INTEGER',
    })
    # We're always in "RiO land", not "RCEP land", for this one.
    add_indexes(engine, args, table, [
        {  # Joint index, for JOIN in UPDATE statement below
            'index_name': CRATE_IDX_RIONUM_NOTENUM,
            'column': '{rio_number}, NoteNum'.format(
                rio_number=CRATE_COL_RIO_NUMBER),
        },
        {  # Speeds up WHERE below. (Much, much faster for second run.)
            'index_name': CRATE_IDX_MAX_SUBNUM,
            'column': CRATE_COL_MAX_SUBNUM,
        },
        {  # Speeds up WHERE below. (Much, much faster for second run.)
            'index_name': CRATE_IDX_LAST_NOTE,
            'column': CRATE_COL_LAST_NOTE,
        },
    ])

    ensure_columns_present(engine, table=table, column_names=[
        "NoteNum", "SubNum", "EnteredInError", "EnteredInError"])
    if not args.print:
        ensure_columns_present(engine, table=table, column_names=[
            CRATE_COL_MAX_SUBNUM, CRATE_COL_LAST_NOTE, CRATE_COL_RIO_NUMBER])

    # Find the maximum SubNum for each note, and store it.
    # Slow query, even with index.
    log.info("Progress notes table '{}': "
             "updating 'max_subnum_for_notenum'".format(table.name))
    execute(engine, args, """
        UPDATE p1
        SET p1.{max_subnum_col} = subq.max_subnum
        FROM {tablename} p1 JOIN (
            SELECT {rio_number}, NoteNum, MAX(SubNum) AS max_subnum
            FROM {tablename} p2
            GROUP BY {rio_number}, NoteNum
        ) subq
        ON subq.{rio_number} = p1.{rio_number}
        AND subq.NoteNum = p1.NoteNum
        WHERE p1.{max_subnum_col} IS NULL
    """.format(
        max_subnum_col=CRATE_COL_MAX_SUBNUM,
        tablename=table.name,
        rio_number=CRATE_COL_RIO_NUMBER,
    ))

    # Set a single column accordingly
    log.info("Progress notes table '{}': "
             "updating 'last_note_in_edit_chain'".format(table.name))
    execute(engine, args, """
        UPDATE {tablename} SET
            {last_note_col} =
                CASE
                    WHEN SubNum = {max_subnum_col} THEN 1
                    ELSE 0
                END
        WHERE {last_note_col} IS NULL
    """.format(
        tablename=table.name,
        last_note_col=CRATE_COL_LAST_NOTE,
        max_subnum_col=CRATE_COL_MAX_SUBNUM,
    ))

    # Create a view
    log.info("Creating view '{}'".format(VIEW_PROGRESS_NOTES_CURRENT))
    select_sql = """
        SELECT *
        FROM {tablename}
        WHERE
            (EnteredInError <> 1 OR EnteredInError IS NULL)
            AND {last_note_col} = 1
    """.format(
        tablename=table.name,
        last_note_col=CRATE_COL_LAST_NOTE,
    )
    create_view(engine, args, VIEW_PROGRESS_NOTES_CURRENT, select_sql)


def drop_for_progress_notes(table, engine, args):
    drop_view(engine, args, VIEW_PROGRESS_NOTES_CURRENT)
    drop_indexes(engine, args, table, [CRATE_IDX_RIONUM_NOTENUM,
                                       CRATE_IDX_MAX_SUBNUM,
                                       CRATE_IDX_LAST_NOTE])
    drop_columns(engine, args, table, [CRATE_COL_MAX_SUBNUM,
                                       CRATE_COL_LAST_NOTE])


# =============================================================================
# RiO view creators
# =============================================================================

def rio_add_user_lookup(select_elements, from_elements,
                        basetable, basecolumn_usercode,
                        column_prefix=None, alias_prefix=None):
    # NOT VERIFIED IN FULL - insufficient data with just top 1000 rows for
    # each table (2016-07-12).
    column_prefix = column_prefix or basecolumn_usercode
    alias_prefix = alias_prefix or "t_" + column_prefix  # table alias
    select_elements.append("""
        {basetable}.{basecolumn_usercode} AS {cp}_user_code,

        {ap}_genhcp.ConsultantFlag AS {cp}_consultant_flag,

        {ap}_genperson.Email AS {cp}_email,
        {ap}_genperson.Title AS {cp}_title,
        {ap}_genperson.FirstName AS {cp}_first_name,
        {ap}_genperson.Surname AS {cp}_surname,

        {ap}_prof.Code AS {cp}_responsible_clinician_profession_code,
        {ap}_prof.CodeDescription AS {cp}_responsible_clinician_profession_description,

        {ap}_serviceteam.Code AS {cp}_primary_team_code,
        {ap}_serviceteam.CodeDescription AS {cp}_primary_team_description,

        {ap}_genspec.Code AS {cp}_main_specialty_code,
        {ap}_genspec.CodeDescription AS {cp}_main_specialty_description,
        {ap}_genspec.NationalCode AS {cp}_main_specialty_national_code,

        {ap}_profgroup.Code AS {cp}_professional_group_code,
        {ap}_profgroup.CodeDescription AS {cp}_professional_group_description,

        {ap}_genorg.Code AS {cp}_organisation_type_code,
        {ap}_genorg.CodeDescription AS {cp}_organisation_type_description

        -- {cp}_location... ?? Presumably from GenLocation, but via what? Seems meaningless.
    """.format(  # noqa
        basetable=basetable,
        basecolumn_usercode=basecolumn_usercode,
        cp=column_prefix,
        ap=alias_prefix,
    ))
    # - User codes are keyed to GenUser.GenUserID, but also to several other
    #   tables, e.g. GenHCP.GenHCPCode; GenPerson.GenPersonID
    # - We use unique table aliases here, so that overall we can make >1 sets
    #   of different "user" joins simultaneously.
    from_elements.append("""
        LEFT JOIN (
            GenHCP {ap}_genhcp
            INNER JOIN GenUser {ap}_genuser
                ON {ap}_genhcp.GenHCPCode = {ap}_genuser.GenUserID
            INNER JOIN GenPerson {ap}_genperson
                ON {ap}_genhcp.GenHCPCode = {ap}_genperson.GenPersonID
            LEFT JOIN GenHCPRCProfession {ap}_prof
                ON {ap}_genhcp.RCProfession = {ap}_prof.Code
            LEFT JOIN GenServiceTeam {ap}_serviceteam
                ON {ap}_genhcp.PrimaryTeam = {ap}_serviceteam.Code
            LEFT JOIN GenSpecialty {ap}_genspec
                ON {ap}_genhcp.MainGenSpecialtyCode = {ap}_genspec.Code
            LEFT JOIN GenStaffProfessionalGroup {ap}_profgroup
                ON {ap}_genhcp.StaffProfessionalGroup = {ap}_profgroup.Code
            LEFT JOIN GenOrganisationType {ap}_genorg
                ON {ap}_genuser.OrganisationType = {ap}_genorg.Code
        ) ON {basetable}.{basecolumn_usercode} = {ap}_genhcp.GenHCPCode
    """.format(  # noqa
        basetable=basetable,
        basecolumn_usercode=basecolumn_usercode,
        ap=alias_prefix,
    ))
    # OTHER THINGS:
    # - GenHCP.Occupation is listed in the RiO docs but doesn't actually seem
    #   to exist. (Perhaps explaining why it's not linked in the RCEP output.)
    #   I had tried to link it to CareCoordinatorOccupation.Code.
    #   If you use:
    #       SELECT *
    #       FROM information_schema.columns
    #       WHERE column_name LIKE '%Occup%'
    #   you only get Client_Demographic_Details.Occupation and
    #   Client_Demographic_Details.Partner_Occupation


def starting_view_elements(engine, basetable):
    select_elements = [
        ", ".join("{}.{}".format(basetable, x)
                  for x in get_column_names(engine, tablename=basetable,
                                            to_lower=True))
    ]
    from_elements = [basetable]
    return select_elements, from_elements


def finish_view_select_sql(select_elements, from_elements):
    return "\n    SELECT {select_elements} FROM {from_elements}".format(
        select_elements=", ".join(select_elements),
        from_elements="\n".join(from_elements)
    )


def rio_view_progress_notes(engine):
    basetable = RIO_TABLE_PROGRESS_NOTES
    select_elements, from_elements = starting_view_elements(engine, basetable)
    rio_add_user_lookup(
        select_elements=select_elements,
        from_elements=from_elements,
        basetable=basetable,
        basecolumn_usercode="EnteredBy",
        column_prefix="originating_user",
        alias_prefix="ou"
    )
    rio_add_user_lookup(
        select_elements=select_elements,
        from_elements=from_elements,
        basetable=basetable,
        basecolumn_usercode="VerifyUserID",
        column_prefix="verifying_user",
        alias_prefix="vu"
    )
    return finish_view_select_sql(select_elements, from_elements)


def get_rio_views(engine):
    # Dictionary of {viewname: select_sql} pairs.
    return {
        'progress_notes_testview': rio_view_progress_notes(engine),
    }


def create_rio_views(engine, args):
    rio_views = get_rio_views(engine)
    for viewname, select_sql in rio_views.items():
        create_view(engine, args, viewname, select_sql)


def drop_rio_views(engine, args):
    rio_views = get_rio_views(engine)
    for viewname, _ in rio_views.items():
        drop_view(engine, args, viewname)


# =============================================================================
# Geography views
# =============================================================================

def add_postcode_geography_view(engine, args):
    # Re-read column names, as we may have inserted some recently by hand that
    # may not be in the initial metadata.
    if args.rio:
        addresstable = RIO_TABLE_ADDRESS
        rio_postcodecol = RIO_COL_POSTCODE
    else:
        addresstable = RCEP_TABLE_ADDRESS
        rio_postcodecol = RCEP_COL_POSTCODE
    orig_column_names = get_column_names(engine, tablename=addresstable,
                                         sort=True)

    # Remove any original column names being overridden by new ones.
    # (Could also do this the other way around!)
    geogcols_lowercase = [x.lower() for x in args.geogcols]
    orig_column_names = [x for x in orig_column_names
                         if x.lower() not in geogcols_lowercase]

    orig_column_specs = [
        "{t}.{c}".format(t=addresstable, c=col)
        for col in orig_column_names
    ]
    geog_col_specs = [
        "{db}.{t}.{c}".format(db=args.postcodedb,
                              t=ONSPD_TABLE_POSTCODE,
                              c=col)
        for col in sorted(args.geogcols, key=lambda x: x.lower())
    ]
    overlap = set(orig_column_names) & set(args.geogcols)
    if overlap:
        die("Columns overlap: address table contains columns {}; "
            "geogcols = {}; overlap = {}".format(
                orig_column_names, args.geogcols, overlap))
    log.info("Creating view '{}'".format(VIEW_ADDRESS_WITH_GEOGRAPHY))
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
        origcols=", ".join(orig_column_specs),
        geogcols=", ".join(geog_col_specs),
        pdb=args.postcodedb,
        pcdtab=ONSPD_TABLE_POSTCODE,
        rio_postcodecol=rio_postcodecol,
    )
    create_view(engine, args, VIEW_ADDRESS_WITH_GEOGRAPHY, select_sql)


# =============================================================================
# Table action selector
# =============================================================================

def process_table(table, engine, args):
    tablename = table.name
    column_names = table.columns.keys()
    log.debug("TABLE: '{}'; COLUMNS: {}".format(tablename, column_names))
    if args.rio:
        patient_table_indicator_column = get_rio_patient_id_col(table)
    else:  # RCEP:
        patient_table_indicator_column = RCEP_COL_PATIENT_ID

    is_patient_table = (patient_table_indicator_column in column_names or
                        tablename == args.full_prognotes_table)
    # ... special for RCEP/CPFT, where a RiO table (with different patient ID
    # column) lives within an RCEP database.
    if args.drop_danger_drop:
        # ---------------------------------------------------------------------
        # DROP STUFF! Opposite order to creation (below)
        # ---------------------------------------------------------------------
        # Specific
        if tablename == args.master_patient_table:
            drop_for_master_patient_table(table, engine, args)
        elif tablename == args.full_prognotes_table:
            drop_for_progress_notes(table, engine, args)
        # Generic
        if is_patient_table:
            drop_for_patient_table(table, engine, args)
        else:
            drop_for_nonpatient_table(table, engine, args)
    else:
        # ---------------------------------------------------------------------
        # CREATE STUFF!
        # ---------------------------------------------------------------------
        # Generic
        if is_patient_table:
            process_patient_table(table, engine, args)
        else:
            process_nonpatient_table(table, engine, args)
        # Specific
        if tablename == args.master_patient_table:
            process_master_patient_table(table, engine, args)
        elif tablename == args.full_prognotes_table:
            process_progress_notes(table, engine, args)


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=
        r"""
*   Alters a RiO database to be suitable for CRATE.

*   By default, this treats the source database as being a copy of a RiO 6.2
    database. Use the "--rcep" (+/- "--cpft") switch(es) to treat it as a
    Servelec RiO CRIS Extract Program (RCEP) v2 output database.
    """)  # noqa
    parser.add_argument("--url", required=True, help="SQLAlchemy database URL")
    parser.add_argument(
        "--print", action="store_true",
        help="Print SQL but do not execute it. (You can redirect the printed "
             "output to create an SQL script.")
    parser.add_argument("--echo", action="store_true", help="Echo SQL")
    parser.add_argument(
        "--rcep", action="store_true",
        help="Treat the source database as the product of Servelec's RiO CRIS "
             "Extract Program v2 (instead of raw RiO)")
    parser.add_argument(
        "--drop_danger_drop", action="store_true",
        help="REMOVES new columns and indexes, rather than creating them.")
    parser.add_argument(
        "--cpft", action="store_true",
        help="Apply hacks for Cambridgeshire & Peterborough NHS Foundation "
             "Trust (CPFT)")
    parser.add_argument(
        "--postcodedb",
        help="Specify database (schema) name for ONS Postcode Database (as "
             "imported by CRATE) to link to addresses as a view")
    parser.add_argument(
        "--geogcols", nargs="*", default=DEFAULT_GEOG_COLS,
        help="List of geographical information columns to link in from ONS "
             "Postcode Database. BEWARE that you do not specify anything too "
             "identifying. Default: {}".format(' '.join(DEFAULT_GEOG_COLS)))
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose")
    args = parser.parse_args()

    configure_logger_for_colour(
        log, level=logging.DEBUG if args.verbose else logging.INFO)

    args.rio = not args.rcep
    if args.rcep:
        # RCEP
        args.master_patient_table = RCEP_TABLE_MASTER_PATIENT
        if args.cpft:
            args.full_prognotes_table = CPFT_RCEP_TABLE_FULL_PROGRESS_NOTES
            # We (CPFT) may have a hacked-in copy of the RiO main progress 
            # notes table added to the RCEP output database. 
        else:
            args.full_prognotes_table = None
            # The RCEP does not export sufficient information to distinguish 
            # current and non-current versions of progress notes.
    else:
        # RiO
        args.master_patient_table = RIO_TABLE_MASTER_PATIENT
        args.full_prognotes_table = RIO_TABLE_PROGRESS_NOTES

    if args.postcodedb and not args.geogcols:
        die("If you specify postcodedb, you must specify some geogcols")

    log.info("CRATE in-place preprocessor for RiO or RiO CRIS Extract Program "
             "(RCEP) databases")
    safeargs = {k: v for k, v in vars(args).items() if k != 'url'}
    log.debug("args = {}".format(repr(safeargs)))
    log.info("RiO mode" if args.rio else "RCEP mode")

    engine = create_engine(args.url, echo=args.echo, encoding=MYSQL_CHARSET)
    metadata.bind = engine
    log.info("Database: {}".format(repr(engine.url)))  # ... repr hides p/w
    log.debug("Dialect: {}".format(engine.dialect.name))

    metadata.reflect(engine)

    for table in sorted(metadata.tables.values(),
                        key=lambda t: t.name.lower()):
        process_table(table, engine, args)
    if args.rio:
        if args.drop_danger_drop:
            drop_rio_views(engine, args)
        else:
            create_rio_views(engine, args)
    if args.postcodedb:
        if args.drop_danger_drop:
            drop_view(engine, args, VIEW_ADDRESS_WITH_GEOGRAPHY)
        else:
            add_postcode_geography_view(engine, args)


if __name__ == '__main__':
    main()
