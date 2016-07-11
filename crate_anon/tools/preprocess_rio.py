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

# Tables in RiO v6.2 Core:
RIO_TABLE_MASTER_PATIENT = "ClientIndex"
RIO_TABLE_ADDRESS = "ClientAddress"
RIO_TABLE_PROGRESS_NOTES = "PrgProgressNote"
# Columns in RiO Core:
RIO_COL_PATIENT_ID = "ClientID"  # RiO 6.2: VARCHAR(15)
RIO_COL_NHS_NUMBER = "NNN"  # RiO 6.2: CHAR(10) ("National NHS Number")
RIO_COL_POSTCODE = "PostCode"  # ClientAddress.PostCode
RIO_COL_PK = "SequenceID"  # INT

# Tables in RiO CRIS Extract Program (RCEP) output database:
RCEP_TABLE_MASTER_PATIENT = "Client_Demographic_Details"
RCEP_TABLE_ADDRESS = "Client_Address_History"
RCEP_TABLE_PROGRESS_NOTES = "Progress_Notes"
# Columns in RCEP extract:
RCEP_COL_PATIENT_ID = "Client_ID"  # RCEP: VARCHAR(15)
RCEP_COL_NHS_NUMBER = "NHS_Number"  # RCEP: CHAR(10)
RCEP_COL_POSTCODE = "Post_Code" # RCEP: NVARCHAR(10)
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
    "msoa11", "parish", "bua11", "bua11sd", "ru11ind",
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

# Views added:
VIEW_PROGRESS_NOTES_CURRENT = "crate_progress_notes_current"
VIEW_ADDRESS_WITH_GEOGRAPHY = "crate_client_address_with_geography"


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

def process_patient_table(table, engine, args):
    log.info("Patient table: '{}'".format(table.name))
    # -------------------------------------------------------------------------
    # Add pk and rio_number columns, if not present
    # -------------------------------------------------------------------------
    if args.rio:
        pktype = 'INTEGER NOT NULL'
    else:  # RCEP
        pktype = 'INTEGER IDENTITY(1, 1) NOT NULL'
    add_columns(engine, args, table, {
        CRATE_COL_PK: pktype,
        CRATE_COL_RIO_NUMBER: 'INTEGER',
    })
    # -------------------------------------------------------------------------
    # Update pk and rio_number values, if not NULL
    # -------------------------------------------------------------------------
    log.info("Table '{}': updating columns '{}' and '{}'".format(
        table.name, CRATE_COL_PK, CRATE_COL_RIO_NUMBER))
    if args.rio or table.name == args.full_prognotes_table:
        # ... the extra condition covering the CPFT hacked-in RiO table within
        # an otherwise RCEP database
        ensure_columns_present(engine, table=table, column_names=[
            RIO_COL_PK, RIO_COL_PATIENT_ID])
        if not args.print:
            ensure_columns_present(engine, table=table, column_names=[
                CRATE_COL_PK, CRATE_COL_RIO_NUMBER])
        execute(engine, args, """
        UPDATE {tablename} SET
            {pk} = {rio_pk},
            {rio_number} = CAST({rio_pt_id} AS INTEGER)
        WHERE
            {pk} IS NULL
            OR {rio_number} IS NULL
    """.format(
            tablename=table.name,
            pk=CRATE_COL_PK,
            rio_pk=RIO_COL_PK,
            rio_number=CRATE_COL_RIO_NUMBER,
            rio_pt_id=RIO_COL_PATIENT_ID,
        ))
    else:
        # RCEP format
        ensure_columns_present(engine, table=table, column_names=[
            RCEP_COL_MANGLED_KEY, RCEP_COL_PATIENT_ID])
        if not args.print:
            ensure_columns_present(engine, table=table, column_names=[
                CRATE_COL_PK, CRATE_COL_RIO_NUMBER])
        execute(engine, args, """
            UPDATE {tablename} SET
                -- pk is autogenerated as an INT IDENTITY field
                {rio_number} = CAST({rcep_pt_id} AS INTEGER)
            WHERE
                {rio_number} IS NULL
        """.format(  # noqa
            tablename=table.name,
            pk=CRATE_COL_PK,
            rcep_mangled_pk=RCEP_COL_MANGLED_KEY,
            rio_number=CRATE_COL_RIO_NUMBER,
            rcep_pt_id=RCEP_COL_PATIENT_ID,
        ))
        """ Chucked:
            {pk} = CAST(
                SUBSTRING(
                    {rcep_mangled_pk},
                    CHARINDEX('_', {rcep_mangled_pk}) + 1,
                    LEN({rcep_mangled_pk}) - CHARINDEX('_', {rcep_mangled_pk})
                ) AS INTEGER
            ),
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
        {
            'index_name': CRATE_IDX_RIONUM_NOTENUM,
            'column': '{rio_number}, NoteNum'.format(
                rio_number=CRATE_COL_RIO_NUMBER),
            # join index, for UPDATE below
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
    drop_indexes(engine, args, table, [CRATE_IDX_RIONUM_NOTENUM])
    drop_columns(engine, args, table, [CRATE_COL_MAX_SUBNUM,
                                       CRATE_COL_LAST_NOTE])


# =============================================================================
# Other view creators
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

    if args.drop_danger_drop:
        # DROP STUFF! Different order
        # Specific
        if tablename == args.master_patient_table:
            drop_for_master_patient_table(table, engine, args)
        elif tablename == args.full_prognotes_table:
            drop_for_progress_notes(table, engine, args)
        # Generic
        if args.patient_table_indicator_column in column_names:
            drop_for_patient_table(table, engine, args)
    else:
        # CREATE STUFF!
        # Generic
        if args.patient_table_indicator_column in column_names:
            process_patient_table(table, engine, args)
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
        args.patient_table_indicator_column = RCEP_COL_PATIENT_ID
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
        args.patient_table_indicator_column = RIO_COL_PATIENT_ID
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
    log.info("Database: {}".format(repr(engine.url))) # ... repr hides password
    log.debug("Dialect: {}".format(engine.dialect.name))

    metadata.reflect(engine)

    for table in sorted(metadata.tables.values(),
                        key=lambda t: t.name.lower()):
        process_table(table, engine, args)
    if args.postcodedb:
        if args.drop_danger_drop:
            drop_view(engine, args, VIEW_ADDRESS_WITH_GEOGRAPHY)
        else:
            add_postcode_geography_view(engine, args)


if __name__ == '__main__':
    main()
