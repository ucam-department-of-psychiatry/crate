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
RCEP_COL_MANGLED_PK = "Document_ID"
# In RCEP, Document_ID is VARCHAR(MAX), and is effectively:
#   'global_table_id_9_or_10_digits' + '_' + 'pk_int_as_string'

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
CRATE_COL_PK = "pk"
CRATE_COL_RIO_NUMBER = "rio_number"
CRATE_COL_NHS_NUMBER = "nhs_number_int"

# Indexes added:
CRATE_IDX_PK = "crate_idx_pk"  # for any patient table
CRATE_IDX_RIONUM = "crate_idx_rionum"  # for any patient table
CRATE_IDX_RIONUM_NOTENUM = "crate_idx_rionum_notenum"  # for Progress Notes

# Views added:
VIEW_PROGRESS_NOTES_CURRENT = "progress_notes_current"
VIEW_ADDRESS_WITH_GEOGRAPHY = "client_address_with_geography"


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
    if args.print:
        print(format_sql_for_print(sql) + "\n;")
        # extra \n in case the SQL ends in a comment
    else:
        engine.execute(sql)


def add_columns_if_absent(engine, args, table, name_coltype_dict):
    column_names = table.columns.keys()
    column_defs = []
    for name, coltype in name_coltype_dict.items():
        if name not in column_names:
            column_defs.append("{} {}".format(name, coltype))
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


def add_index_if_absent(engine, args, table, indexdictlist):
    existing_index_names = get_index_names(engine, table=table)
    for idxdefdict in indexdictlist:
        index_name = idxdefdict['index_name']
        column = idxdefdict['column']
        unique = idxdefdict.get('unique', False)
        if index_name not in existing_index_names:
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


def get_column_names(engine, tablename=None, table=None):
    """
    Reads columns names afresh from the database (in case metadata is out of
    date.
    """
    assert (table is not None) != bool(tablename), "Need table XOR tablename"
    tablename = tablename or table.name
    inspector = inspect(engine)
    columns = inspector.get_columns(tablename)
    column_names = [x['name'] for x in columns]
    return column_names


def get_index_names(engine, tablename=None, table=None):
    """
    Reads index names from the database.
    """
    # http://docs.sqlalchemy.org/en/latest/core/reflection.html
    assert (table is not None) != bool(tablename), "Need table XOR tablename"
    tablename = tablename or table.name
    inspector = inspect(engine)
    indexes = inspector.get_indexes(tablename)
    index_names = [x['name'] for x in indexes]
    return index_names


def ensure_columns_present(engine, table=None, tablename=None, column_names=None):
    assert column_names, "Need column_names"
    assert (table is not None) != bool(tablename), "Need table XOR tablename"
    tablename = tablename or table.name
    existing_column_names = get_column_names(engine, tablename=tablename)
    for col in column_names:
        if col not in existing_column_names:
            die("Column '{}' missing from table '{}'".format(col, tablename))


# =============================================================================
# Generic table processors
# =============================================================================

def process_patient_table(table, engine, args):
    log.info("Patient table: '{}'".format(table.name))
    # -------------------------------------------------------------------------
    # Add pk and rio_number columns, if not present
    # -------------------------------------------------------------------------
    add_columns_if_absent(engine, args, table, {
        CRATE_COL_PK: 'INTEGER',
        CRATE_COL_RIO_NUMBER: 'INTEGER',
    })
    # -------------------------------------------------------------------------
    # Update pk and rio_number values, if not NULL
    # -------------------------------------------------------------------------
    log.info("Table '{}': updating columns '{}' and '{}'".format(
        table.name, CRATE_COL_PK, CRATE_COL_RIO_NUMBER))
    column_names = get_column_names(engine, table=table)
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
            RCEP_COL_MANGLED_PK, RCEP_COL_PATIENT_ID])
        if not args.print:
            ensure_columns_present(engine, table=table, column_names=[
                CRATE_COL_PK, CRATE_COL_RIO_NUMBER])
        execute(engine, args, """
            UPDATE {tablename} SET
                {pk} = CAST(
                    SUBSTRING(
                        {rcep_mangled_pk},
                        CHARINDEX('_', {rcep_mangled_pk}) + 1,
                        LEN({rcep_mangled_pk}) - CHARINDEX('_', {rcep_mangled_pk})
                    ) AS INTEGER
                ),
                {rio_number} = CAST({rcep_pt_id} AS INTEGER)
            WHERE
                {pk} IS NULL
                OR {rio_number} IS NULL
        """.format(
            tablename=table.name,
            pk=CRATE_COL_PK,
            rcep_mangled_pk=RCEP_COL_MANGLED_PK,
            rio_number=CRATE_COL_RIO_NUMBER,
            rcep_pt_id=RCEP_COL_PATIENT_ID,
        ))
    # -------------------------------------------------------------------------
    # Add indexes, if absent
    # -------------------------------------------------------------------------
    # Note that the indexes are unlikely to speed up the WHERE NOT NULL search
    # above, so it doesn't matter that we add these last. Their use is for
    # the subsequent CRATE anonymisation table scans.
    add_index_if_absent(engine, args, table, [
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


# =============================================================================
# Specific table processors
# =============================================================================

def process_master_patient_table(table, engine, args):
    add_columns_if_absent(engine, args, table, {
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


def process_progress_notes(table, engine, args):
    add_columns_if_absent(engine, args, table, {
        'max_subnum_for_notenum': 'INTEGER',
        'last_note_in_edit_chain': 'INTEGER',
    })
    # We're always in "RiO land", not "RCEP land", for this one.
    add_index_if_absent(engine, args, table, [
        {
            'index_name': CRATE_IDX_RIONUM_NOTENUM,
            'column': 'rio_number, NoteNum',  # join index, for UPDATE below
        },
    ])

    ensure_columns_present(engine, table=table, column_names=[
        "NoteNum", "SubNum", "EnteredInError", "EnteredInError"])
    if not args.print:
        ensure_columns_present(engine, table=table, column_names=[
            "max_subnum_for_notenum", "last_note_in_edit_chain", "rio_number"])

    # Find the maximum SubNum for each note, and store it.
    # Slow query, even with index.
    log.info("Progress notes table '{}': "
             "updating 'max_subnum_for_notenum'".format(table.name))
    execute(engine, args, """
        UPDATE p1
        SET p1.max_subnum_for_notenum = subq.max_subnum
        FROM {tablename} p1 JOIN (
            SELECT rio_number, NoteNum, MAX(SubNum) AS max_subnum
            FROM {tablename} p2
            GROUP BY rio_number, NoteNum
        ) subq
        ON subq.rio_number = p1.rio_number
        AND subq.NoteNum = p1.NoteNum
        WHERE p1.max_subnum_for_notenum IS NULL
    """.format(tablename=table.name))

    # Set a single column accordingly
    log.info("Progress notes table '{}': "
             "updating 'last_note_in_edit_chain'".format(table.name))
    execute(engine, args, """
        UPDATE {tablename} SET
            last_note_in_edit_chain =
                CASE
                    WHEN SubNum = max_subnum_for_notenum THEN 1
                    ELSE 0
                END
        WHERE last_note_in_edit_chain IS NULL
    """.format(tablename=table.name))

    # Create a view
    log.info("Creating view '{}'".format(VIEW_PROGRESS_NOTES_CURRENT))
    execute(engine, args, """
        CREATE VIEW {viewname} AS
            SELECT *
            FROM {tablename}
            WHERE
                (EnteredInError <> 1 OR EnteredInError IS NULL)
                AND last_note_in_edit_chain = 1
    """.format(viewname=VIEW_PROGRESS_NOTES_CURRENT, tablename=table.name))


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
    orig_column_names = get_column_names(engine, tablename=addresstable)
    orig_column_specs = [
        "{t}.{c}".format(t=addresstable, c=col)
        for col in orig_column_names
    ]
    geog_col_specs = [
        "{db}.{t}.{c}".format(db=args.postcodedb,
                              t=ONSPD_TABLE_POSTCODE,
                              c=col)
        for col in args.geogcols
    ]
    overlap = set(orig_column_names) & set(args.geogcols)
    if overlap:
        die("Columns overlap: address table contains columns {}; "
            "geogcols = {}; overlap = {}".format(
                orig_column_names, args.geogcols, overlap))
    log.info("Creating view '{}'".format(VIEW_ADDRESS_WITH_GEOGRAPHY))
    ensure_columns_present(engine, tablename=addresstable, column_names=[
        rio_postcodecol])
    execute(engine, args, """
        CREATE VIEW {viewname} AS
            SELECT {origcols},
                   {geogcols}
            FROM {addresstable}
            LEFT JOIN {pdb}.{pcdtab}
            ON REPLACE({addresstable}.{rio_postcodecol},
                       ' ',
                       '') = {pdb}.{pcdtab}.pcd_nospace
            -- Since we can't guarantee RiO's postcode space formatting, from
            -- NVARCHAR(10) columns, we compare to the no-space version.
    """.format(  # noqa
        viewname=VIEW_ADDRESS_WITH_GEOGRAPHY,
        addresstable=addresstable,
        origcols=", ".join(orig_column_specs),
        geogcols=", ".join(geog_col_specs),
        pdb=args.postcodedb,
        pcdtab=ONSPD_TABLE_POSTCODE,
        rio_postcodecol=rio_postcodecol,
    ))


# =============================================================================
# Table action selector
# =============================================================================

def process_table(table, engine, args):
    tablename = table.name
    column_names = table.columns.keys()
    log.debug("TABLE: '{}'; COLUMNS: {}".format(tablename, column_names))

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

    metadata.reflect(engine)

    for table in sorted(metadata.tables.values(), key=lambda t: t.name):
        process_table(table, engine, args)
    if args.postcodedb:
        add_postcode_geography_view(engine, args)


if __name__ == '__main__':
    main()
