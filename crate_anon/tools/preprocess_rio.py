#!/usr/bin/env python
# crate_anon/tools/preprocess_rio.py

import argparse
import logging

from sqlalchemy import (
    Column,
    create_engine,
    Date,
    inspect,
    Integer,
    MetaData,
    Numeric,
    String,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from crate_anon.anonymise.constants import MYSQL_CHARSET
from crate_anon.anonymise.logsupport import configure_logger_for_colour

log = logging.getLogger(__name__)
metadata = MetaData()

# Tables in RiO v6.2 Core:
RIO_TABLE_MASTER_PATIENT = "ClientIndex"
RIO_TABLE_ADDRESS = "ClientAddress"
RIO_TABLE_PROGRESS_NOTES = "PrgProgressNote"

# Tables in RiO CRIS Extract Program (RCEP) output database:
RCEP_TABLE_MASTER_PATIENT = "Client_Demographic_Details"
RCEP_TABLE_ADDRESS = "***" # ***
RCEP_TABLE_PROGRESS_NOTES = "Progress_Notes"

# CPFT hacks (RiO tables added to RCEP output):
CPFT_RCEP_TABLE_FULL_PROGRESS_NOTES = "Progress_Notes_II"

# Columns in RiO Core:
# RIO_COL_INDICATING_PATIENT_TABLE = "ClientID"  # RiO 6.2: VARCHAR(15)
RIO_COL_INDICATING_PATIENT_TABLE = "pct_code"
RIO_COL_NHS_NUMBER = "NNN"  # RiO 6.2: CHAR(10) ("National NHS Number")
RIO_COL_POSTCODE = "PostCode"  # ClientAddress.PostCode

# Columns in RCEP extract:
# RCEP_COL_INDICATING_PATIENT_TABLE = "Client_ID"  # RCEP: VARCHAR(15)
RCEP_COL_INDICATING_PATIENT_TABLE = "pct_code"
RCEP_COL_NHS_NUMBER = "NHS_Number"  # RCEP: CHAR(10)
RCEP_COL_POSTCODE = "***"

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

def execute(engine, sql):
    log.debug(sql)
    # engine.execute(sql)


def add_columns_if_absent(engine, table, name_coltype_dict):
    column_names = table.columns.keys()
    add_fragments = []
    for name, coltype in name_coltype_dict.items():
        if name not in column_names:
            add_fragments.append("{} {}".format(name, coltype))
    if add_fragments:
        log.info("Table '{}': adding columns {}".format(
            table.name, repr(add_fragments)))
        execute(engine, """
            ALTER TABLE {tablename} ADD {fragments}
        """.format(tablename=table.name, fragments=", ".join(add_fragments)))


def add_index_if_absent(engine, table, indexdictlist):
    inspector = inspect(engine)
    indexes = inspector.get_indexes(table.name)
    existing_index_names = [x['name'] for x in indexes]
    # http://docs.sqlalchemy.org/en/latest/core/reflection.html
    for idxdefdict in indexdictlist:
        index_name = idxdefdict['index_name']
        column = idxdefdict['column']
        unique = idxdefdict.get('unique', False)
        if index_name not in existing_index_names:
            log.info("Table '{}': adding index '{}' on columns '{}'".format(
                table.name, index_name, column))
            execute(engine, """
              CREATE {unique} INDEX {idxname} ON {tablename} ({column})
            """.format(
                unique="UNIQUE" if unique else "",
                idxname=index_name,
                tablename=table.name,
                column=column,
            ))


# =============================================================================
# Generic table processors
# =============================================================================

def process_patient_table(table, engine, args):
    log.info("Patient table: '{}'".format(table.name))
    # -------------------------------------------------------------------------
    # Add pk and rio_number columns, if not present
    # -------------------------------------------------------------------------
    add_columns_if_absent(engine, table, {
        CRATE_COL_PK: 'INTEGER',
        CRATE_COL_RIO_NUMBER: 'INTEGER',
    })
    # -------------------------------------------------------------------------
    # Update pk and rio_number values, if not NULL
    # -------------------------------------------------------------------------
    log.info("Table {}: updating columns {}, {}".format(
        table.name, CRATE_COL_PK, CRATE_COL_RIO_NUMBER))
    if args.rio or table.name == args.full_prognotes_table:
        # ... the extra condition covering the CPFT hacked-in RiO table within
        # an otherwise RCEP database
        execute(engine, """
        UPDATE {tablename} SET
            {pk} = SequenceID,  -- PK in RiO 6.2; INT
            {rio_number} = CAST(ClientID AS INTEGER)  -- ClientID VARCHAR(15)
        WHERE
            {pk} IS NULL
            OR {rio_number} IS NULL
    """.format(
            tablename=table.name,
            pk=CRATE_COL_PK,
            rio_number=CRATE_COL_RIO_NUMBER,
        ))
    else:
        # RCEP format
        execute(engine, """
            UPDATE {tablename} SET
                -- In RCEP, Document_ID is VARCHAR(MAX), and is effectively:
                -- 'global_table_id_9_or_10_digits' + '_' + 'pk_int_as_string'
                {pk} = CAST(
                    SUBSTRING(
                        Document_ID,
                        CHARINDEX('_', Document_ID) + 1,
                        LEN(Document_ID) - CHARINDEX('_', Document_ID)
                    ) AS INTEGER
                ),
                -- RCEP: Client_ID VARCHAR(15)
                {rio_number} = CAST(Client_ID AS INTEGER)
            WHERE
                {pk} IS NULL
                OR {rio_number} IS NULL
        """.format(
            tablename=table.name,
            pk=CRATE_COL_PK,
            rio_number=CRATE_COL_RIO_NUMBER,
        ))
    # -------------------------------------------------------------------------
    # Add indexes, if absent
    # -------------------------------------------------------------------------
    add_index_if_absent(engine, table, [
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
    add_columns_if_absent(engine, table, {
        'nhs_number_int': 'BIGINT',
    })
    if args.rcep:
        nhscol = RCEP_COL_NHS_NUMBER
    else:
        nhscol = RIO_COL_NHS_NUMBER
    log.info("Table {}: updating columns {}, {}".format(table.name, nhscol))
    execute(engine, """
        UPDATE {tablename} SET
            nhs_number_int = CAST({nhscol}} AS BIGINT)
    """.format(
        tablename=table.name,
        nhsfield=nhscol,
    ))


def process_progress_notes(table, engine, args):
    add_columns_if_absent(engine, table, {
        'max_subnum_for_notenum': 'INTEGER',
        'last_note_in_edit_chain': 'INTEGER',
    })
    # We're always in "RiO land", not "RCEP land", for this one.
    add_index_if_absent(engine, table, [
        {
            'index_name': CRATE_IDX_RIONUM_NOTENUM,
            'column': 'rio_number, NoteNum',  # join index, for UPDATE below
        },
    ])

    # Find the maximum SubNum for each note, and store it.
    # Slow query, even with index.
    log.info("Progress notes table '{}': "
             "updating 'max_subnum_for_notenum'".format(table.name))
    execute(engine, """
        UPDATE p1
        SET p1.max_subnum_for_notenum = subq.max_subnum
        FROM {tablename} p1 JOIN (
            SELECT rio_number, NoteNum, MAX(SubNum) AS max_subnum
            FROM {tablename} p2
            GROUP BY rio_number, NoteNum
        ) subq
        ON subq.rio_number = p1.rio_number
        AND subq.NoteNum = p1.NoteNum
        WHERE p1.max_subnum_for_notenum IS NULL;
    """.format(tablename=table.name))

    # Set a single column accordingly
    log.info("Progress notes table '{}': "
             "updating 'last_note_in_edit_chain'".format(table.name))
    execute(engine, """
        UPDATE {tablename} SET
            last_note_in_edit_chain =
                CASE
                    WHEN SubNum = max_subnum_for_notenum THEN 1
                    ELSE 0
                END
        WHERE last_note_in_edit_chain IS NULL;
    """.format(tablename=table.name))

    # Create a view
    log.info("Creating view '{}'".format(VIEW_PROGRESS_NOTES_CURRENT))
    execute(engine, """
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
    inspector = inspect(engine)
    orig_columns = inspector.get_columns(addresstable)
    orig_column_names = [x['name'] for x in orig_columns]
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
        raise ValueError(
            "Columns overlap: address table contains columns {}; "
            "geogcols = {}; overlap = {}".format(
                orig_column_names, args.geogcols, overlap))
    log.info("Creating view '{}'".format(VIEW_ADDRESS_WITH_GEOGRAPHY))
    execute(engine, """
        CREATE VIEW {viewname} AS
            SELECT {origcols},
                   {geogcols}
            FROM {addrtab}
            LEFT JOIN {pdb}.{pcdtab}
            ON REPLACE({addrtab}.{rio_postcodecol},
                       ' ',
                       '') = {pdb}.{pcdtab}.pcd_nospace
            -- Since we can't guarantee RiO's postcode space formatting,
            -- we compare to the no-space version.
    """.format(  # noqa
        viewname=VIEW_ADDRESS_WITH_GEOGRAPHY,
        addrtab=addresstable,
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
    log.debug("TABLE: {}; COLUMNS: {}".format(tablename, column_names))

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
-   Alters a RiO database to be suitable for CRATE.

-   By default, this treats the source database as being a copy of a RiO 6.2
    database. Use the "--rcep" (+/- "--cpft") switches to treat it as a
    Servelec RiO CRIS Extract Program (RCEP) v2 output database.
    """)  # noqa
    parser.add_argument("--url", required=True, help="SQLAlchemy database URL")
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
        help="List of columns to link in from ONS Postcode Database. BEWARE "
             "that you do not specify anything too identifying. Default: "
             "{}".format(DEFAULT_GEOG_COLS))
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose")
    args = parser.parse_args()

    configure_logger_for_colour(
        log, level=logging.DEBUG if args.verbose else logging.INFO)

    args.rio = not args.rcep
    if args.rcep:
        args.master_patient_table = RIO_TABLE_MASTER_PATIENT
        args.patient_table_indicator_column = RCEP_COL_INDICATING_PATIENT_TABLE
        if args.cpft:
            args.full_prognotes_table = CPFT_RCEP_TABLE_FULL_PROGRESS_NOTES
            # We (CPFT) may have a hacked-in copy of the RiO main progress 
            # notes table added to the RCEP output database. 
        else:
            args.full_prognotes_table = None
            # The RCEP does not export sufficient information to distinguish 
            # current and non-current versions of progress notes.
    else:
        args.master_patient_table = RCEP_TABLE_MASTER_PATIENT
        args.patient_table_indicator_column = RIO_COL_INDICATING_PATIENT_TABLE
        args.full_prognotes_table = RIO_TABLE_PROGRESS_NOTES

    if args.postcodedb and not args.geogcols:
        raise ValueError("If you specify postcodedb, you must specify some "
                         "geogcols")

    log.debug("args = {}".format(repr(args)))

    engine = create_engine(args.url, echo=args.echo, encoding=MYSQL_CHARSET)
    metadata.bind = engine

    metadata.reflect(engine)

    for table in metadata.tables.values():
        process_table(table, engine, args)
    if args.postcodedb:
        add_postcode_geography_view(engine, args)


if __name__ == '__main__':
    main()
