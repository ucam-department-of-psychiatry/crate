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

# Tables in RiO Core:
RIO_MASTER_PATIENT_TABLE = "Client_Demographic_Details"
RIO_PROGRESS_NOTES_TABLE = "Progress_Notes"

# Fields in RiO Core:
RIO_FIELD_INDICATING_PATIENT_TABLE = "Client_ID"

# Views added:
VIEW_PROGRESS_NOTES_CURRENT = "progress_notes_current"


# =============================================================================
# Ancillary functions
# =============================================================================

def execute(engine, sql):
    log.critical(sql)
    # engine.execute(sql)


def add_fields_if_absent(engine, table, name_coltype_dict):
    column_names = table.columns.keys()
    add_fragments = []
    for name, coltype in name_coltype_dict.items():
        if name not in column_names:
            add_fragments.append("{} {}".format(name, coltype))
    if add_fragments:
        execute(engine, """
            ALTER TABLE {tablename} ADD {fragments}
        """.format(tablename=table.name, fragments=", ".join(add_fragments)))


def add_index_if_absent(engine, table, indexes):
    inspector = inspect(engine)
    indexes = inspector.get_indexes(table.name)
    existing_index_names = [x['name'] for x in indexes]
    # http://docs.sqlalchemy.org/en/latest/core/reflection.html
    for idxdefdict in indexes:
        index_name = idxdefdict['index_name']
        column = idxdefdict['column']
        unique = idxdefdict.get('unique', False)
        if index_name not in existing_index_names:
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

def process_patient_table(table, engine):
    log.info("Patient table: ")
    # -------------------------------------------------------------------------
    # Add pk and rio_number fields, if not present
    # -------------------------------------------------------------------------
    add_fields_if_absent(engine, table, {
        'pk': 'INTEGER',
        'rio_number': 'INTEGER',
    })
    # -------------------------------------------------------------------------
    # Update pk and rio_number values, if not NULL
    # -------------------------------------------------------------------------
    # ******* CHECK Document_ID is PK; that may be a tool thing, not source database
    # ******* if it is, disable this (sensibly) for Progress_Notes, which uses SequenceID
    execute(engine, """
        UPDATE {tablename} SET
            pk = CAST(SUBSTRING(Document_ID,
                                CHARINDEX('_', Document_ID) + 1,
                                LEN(Document_ID) - CHARINDEX('_', Document_ID))
                      AS INTEGER),
            rio_number = CAST(Client_ID AS INTEGER)
        WHERE
            pk IS NULL
            OR rio_number IS NULL
    """.format(tablename=table.name))
    # -------------------------------------------------------------------------
    # Add indexes, if absent
    # -------------------------------------------------------------------------
    add_index_if_absent(engine, table, [
        {
            'index_name': 'crate_idx_pk',
            'column': 'pk',
            'unique': True,
        },
        {
            'index_name': 'crate_idx_rionum',
            'column': 'rio_number',
        },
    ])


# =============================================================================
# Specific table processors
# =============================================================================

def process_master_patient_table(table, engine):
    add_fields_if_absent(engine, table, {
        'nhs_number_int': 'BIGINT',
    })
    execute(engine, """
        UPDATE {tablename} SET
            nhs_number_int = CAST(NHS_Number AS BIGINT)
    """.format(tablename=table.name))


def process_progress_notes(table, engine):
    add_fields_if_absent(engine, table, {
        'max_subnum_for_notenum': 'INTEGER',
        'last_note_in_edit_chain': 'INTEGER',
    })
    execute(engine, """
        UPDATE {tablename} SET
            pk = SequenceID
    """.format(tablename=table.name))
    add_index_if_absent(engine, table, [
        {
            'index_name': 'crate_idx_rionum_notenum',
            'column': 'rio_number, NoteNum',  # join index, for UPDATE below
        },
    ])

    # Find the maximum SubNum for each note, and store it.
    # Slow query, even with index.
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

    # Set a single field accordingly
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
    execute(engine, """
        CREATE VIEW {viewname} AS
            SELECT *
            FROM {tablename}
            WHERE
                (EnteredInError <> 1 OR EnteredInError IS NULL)
                AND last_note_in_edit_chain = 1
    """.format(viewname=VIEW_PROGRESS_NOTES_CURRENT, tablename=table.name))


# =============================================================================
# View creators
# =============================================================================

# *** Progress_Notes with: NOT(EnteredInError = 1 [NULL also OK]) AND last_note_in_edit_chain = 1

# =============================================================================
# Table action selector
# =============================================================================

def process_table(table, engine):
    tablename = table.name
    column_names = table.columns.keys()
    log.info("TABLE: {}; COLUMNS: {}".format(tablename, column_names))
    # Generic
    if RIO_FIELD_INDICATING_PATIENT_TABLE in column_names or True:
        process_patient_table(table, engine)
    # Specific
    if tablename == RIO_MASTER_PATIENT_TABLE:
        process_master_patient_table(table, engine)
    elif tablename == RIO_PROGRESS_NOTES_TABLE:
        process_progress_notes(table, engine)


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=
        r"""
-   Alters a RiO database to be suitable for CRATE.
    """)  # noqa
    parser.add_argument("--url", required=True, help="SQLAlchemy database URL")
    parser.add_argument("--echo", action="store_true", help="Echo SQL")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose")
    args = parser.parse_args()
    configure_logger_for_colour(
        log, level=logging.DEBUG if args.verbose else logging.INFO)
    log.debug("args = {}".format(repr(args)))

    engine = create_engine(args.url, echo=args.echo, encoding=MYSQL_CHARSET)
    metadata.bind = engine

    metadata.reflect(engine)

    for table in metadata.tables.values():
        process_table(table, engine)


if __name__ == '__main__':
    main()
