#!/usr/bin/env python

"""
crate_anon/preprocess/preprocess_rio.py

===============================================================================

    Copyright (C) 2015-2018 Rudolf Cardinal (rudolf@pobox.com).

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

"""

import argparse
import logging
from typing import Any, List

from cardinal_pythonlib.debugging import pdb_run
from cardinal_pythonlib.logs import configure_logger_for_colour
from cardinal_pythonlib.sqlalchemy.schema import (
    get_effective_int_pk_col,
    hack_in_mssql_xml_type,
    make_bigint_autoincrement_column,
)
from sqlalchemy import (
    create_engine,
    MetaData,
)
from sqlalchemy.engine.base import Engine
from sqlalchemy.schema import Column, Table
from sqlalchemy.sql.sqltypes import BigInteger, Integer

from crate_anon.anonymise.constants import CHARSET
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
from crate_anon.preprocess.rio_constants import (
    CPFT_RCEP_TABLE_FULL_PROGRESS_NOTES,
    CRATE_COL_LAST_DOC,
    CRATE_COL_LAST_NOTE,
    CRATE_COL_MAX_DOCVER,
    CRATE_COL_MAX_SUBNUM,
    CRATE_COL_NHS_NUMBER,
    CRATE_COL_PK,
    CRATE_COL_RIO_NUMBER,
    CRATE_IDX_LAST_DOC,
    CRATE_IDX_LAST_NOTE,
    CRATE_IDX_MAX_DOCVER,
    CRATE_IDX_MAX_SUBNUM,
    CRATE_IDX_PK,
    CRATE_IDX_RIONUM,
    CRATE_IDX_RIONUM_NOTENUM,
    CRATE_IDX_RIONUM_SERIALNUM,
    DEFAULT_GEOG_COLS,
    ONSPD_TABLE_POSTCODE,
    RCEP_COL_NHS_NUMBER,
    RCEP_COL_PATIENT_ID,
    RCEP_COL_POSTCODE,
    RCEP_TABLE_ADDRESS,
    RCEP_TABLE_MASTER_PATIENT,
    RIO_COL_NHS_NUMBER,
    RIO_COL_PATIENT_ID,
    RIO_COL_POSTCODE,
    RIO_TABLE_ADDRESS,
    RIO_TABLE_CLINICAL_DOCUMENTS,
    RIO_TABLE_MASTER_PATIENT,
    RIO_TABLE_PROGRESS_NOTES,
    VIEW_ADDRESS_WITH_GEOGRAPHY,
    VIEW_RCEP_CPFT_PROGRESS_NOTES_CURRENT,
)
from crate_anon.preprocess.rio_ddgen import (
    DDHint,
    get_rio_dd_settings,
)
from crate_anon.preprocess.rio_pk import (
    RIO_6_2_ATYPICAL_PATIENT_ID_COLS,
)
from crate_anon.preprocess.rio_view_func import rio_add_audit_info
from crate_anon.preprocess.rio_views import RIO_VIEWS

log = logging.getLogger(__name__)


# =============================================================================
# Generic table processors
# =============================================================================

def table_is_rio_type(tablename: str,
                      progargs: Any) -> bool:
    if progargs.rio:
        return True
    if not progargs.cpft:
        return False
    # RCEP + CPFT modifications: there's one RiO table in the mix
    return tablename == progargs.full_prognotes_table


def get_rio_patient_id_col(table: Table) -> str:
    patient_id_col = RIO_6_2_ATYPICAL_PATIENT_ID_COLS.get(table.name,
                                                          RIO_COL_PATIENT_ID)
    # log.debug("get_rio_patient_id_col: {} -> {}".format(table.name,
    #                                                     patient_id_col))
    return patient_id_col


def process_patient_table(table: Table, engine: Engine, progargs: Any) -> None:
    log.info("Preprocessing patient table: {}".format(repr(table.name)))
    rio_type = table_is_rio_type(table.name, progargs)
    if rio_type:
        pk_col = get_effective_int_pk_col(table)
        rio_pk = pk_col if pk_col != CRATE_COL_PK else None
        string_pt_id = get_rio_patient_id_col(table)
        required_cols = [string_pt_id]
    else:  # RCEP type
        rio_pk = None
        required_cols = [RCEP_COL_PATIENT_ID]
        string_pt_id = RCEP_COL_PATIENT_ID
    if not progargs.print:
        required_cols.extend([CRATE_COL_PK, CRATE_COL_RIO_NUMBER])

    # -------------------------------------------------------------------------
    # Add pk and rio_number columns, if not present
    # -------------------------------------------------------------------------
    if rio_type and rio_pk is not None:
        crate_pk_col = Column(CRATE_COL_PK, BigInteger, nullable=True)
        # ... can't do NOT NULL; need to populate it
        required_cols.append(rio_pk)
    else:  # RCEP type, or no PK in RiO
        crate_pk_col = make_bigint_autoincrement_column(CRATE_COL_PK,
                                                        engine.dialect)
        # ... autopopulates
    crate_rio_number_col = Column(CRATE_COL_RIO_NUMBER, BigInteger,
                                  nullable=True)
    # ... even if RiO numbers are INT, they come from VARCHAR(15) here, and
    # that can (aod does) look numeric and overflow an INT.
    # SQL Server requires Table-bound columns in order to generate DDL:
    table.append_column(crate_pk_col)
    table.append_column(crate_rio_number_col)
    add_columns(engine, table, [crate_pk_col, crate_rio_number_col])

    # -------------------------------------------------------------------------
    # Update pk and rio_number values, if not NULL
    # -------------------------------------------------------------------------
    ensure_columns_present(engine, tablename=table.name,
                           column_names=required_cols)
    cast_id_to_int = sql_fragment_cast_to_int(string_pt_id,
                                              dialect=engine.dialect)
    if rio_type and rio_pk:
        log.info("Table {}: updating columns {} and {}".format(
            repr(table.name), repr(CRATE_COL_PK), repr(CRATE_COL_RIO_NUMBER)))
        execute(engine, """
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
        log.info("Table {}: updating column {}".format(
            repr(table.name), repr(CRATE_COL_RIO_NUMBER)))
        execute(engine, """
            UPDATE {tablename} SET
                {crate_rio_number} = {cast_id_to_int}
            WHERE
                {crate_rio_number} IS NULL
        """.format(  # noqa
            tablename=table.name,
            crate_rio_number=CRATE_COL_RIO_NUMBER,
            cast_id_to_int=cast_id_to_int,
        ))
    # -------------------------------------------------------------------------
    # Add indexes, if absent
    # -------------------------------------------------------------------------
    # Note that the indexes are unlikely to speed up the WHERE NOT NULL search
    # above, so it doesn't matter that we add these last. Their use is for
    # the subsequent CRATE anonymisation table scans.
    add_indexes(engine, table, [
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


def drop_for_patient_table(table: Table, engine: Engine) -> None:
    drop_indexes(engine, table, [CRATE_IDX_PK, CRATE_IDX_RIONUM])
    drop_columns(engine, table, [CRATE_COL_PK, CRATE_COL_RIO_NUMBER])


def process_nonpatient_table(table: Table,
                             engine: Engine,
                             progargs: Any) -> None:
    if progargs.rcep:
        return
    log.info("Preprocessing non-patient table {}".format(repr(table.name)))
    pk_col = get_effective_int_pk_col(table)
    other_pk_col = pk_col if pk_col != CRATE_COL_PK else None
    if other_pk_col:  # table has a primary key already
        crate_pk_col = Column(CRATE_COL_PK, BigInteger, nullable=True)
    else:
        crate_pk_col = make_bigint_autoincrement_column(CRATE_COL_PK,
                                                        engine.dialect)
    table.append_column(crate_pk_col)  # must be Table-bound, as above
    add_columns(engine, table, [crate_pk_col])
    if not progargs.print:
        ensure_columns_present(engine, tablename=table.name,
                               column_names=[CRATE_COL_PK])
    if other_pk_col:
        execute(engine, """
            UPDATE {tablename} SET {crate_pk} = {rio_pk}
            WHERE {crate_pk} IS NULL
        """.format(tablename=table.name,
                   crate_pk=CRATE_COL_PK,
                   rio_pk=other_pk_col))
    add_indexes(engine, table, [{'index_name': CRATE_IDX_PK,
                                 'column': CRATE_COL_PK,
                                 'unique': True}])


def drop_for_nonpatient_table(table: Table, engine: Engine) -> None:
    drop_indexes(engine, table, [CRATE_IDX_PK])
    drop_columns(engine, table, [CRATE_COL_PK])


# =============================================================================
# Specific table processors
# =============================================================================

def process_master_patient_table(table: Table,
                                 engine: Engine,
                                 progargs: Any) -> None:
    crate_col_nhs_number = Column(CRATE_COL_NHS_NUMBER, BigInteger,
                                  nullable=True)
    table.append_column(crate_col_nhs_number)
    add_columns(engine, table, [crate_col_nhs_number])
    if progargs.rcep:
        nhscol = RCEP_COL_NHS_NUMBER
    else:
        nhscol = RIO_COL_NHS_NUMBER
    log.info("Table {}: updating column {}".format(repr(table.name),
                                                   repr(nhscol)))
    ensure_columns_present(engine, tablename=table.name,
                           column_names=[nhscol])
    if not progargs.print:
        ensure_columns_present(engine, tablename=table.name,
                               column_names=[CRATE_COL_NHS_NUMBER])
    execute(engine, """
        UPDATE {tablename} SET
            {nhs_number_int} = CAST({nhscol} AS BIGINT)
            WHERE {nhs_number_int} IS NULL
    """.format(
        tablename=table.name,
        nhs_number_int=CRATE_COL_NHS_NUMBER,
        nhscol=nhscol,
    ))


def drop_for_master_patient_table(table: Table, engine: Engine) -> None:
    drop_columns(engine, table, [CRATE_COL_NHS_NUMBER])


def process_progress_notes(table: Table,
                           engine: Engine,
                           progargs: Any) -> None:
    crate_col_max_subnum = Column(CRATE_COL_MAX_SUBNUM, Integer, nullable=True)
    crate_col_last_note = Column(CRATE_COL_LAST_NOTE, Integer, nullable=True)
    table.append_column(crate_col_max_subnum)
    table.append_column(crate_col_last_note)
    add_columns(engine, table, [crate_col_max_subnum, crate_col_last_note])
    # We're always in "RiO land", not "RCEP land", for this one.
    add_indexes(engine, table, [
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

    ensure_columns_present(engine, tablename=table.name, column_names=[
        "NoteNum", "SubNum", "EnteredInError", "EnteredInError"])
    if not progargs.print:
        ensure_columns_present(engine, tablename=table.name, column_names=[
            CRATE_COL_MAX_SUBNUM, CRATE_COL_LAST_NOTE, CRATE_COL_RIO_NUMBER])

    # Find the maximum SubNum for each note, and store it.
    # Slow query, even with index.
    log.info("Progress notes table {}: updating {}".format(
        repr(table.name), repr(CRATE_COL_MAX_SUBNUM)))
    execute(engine, """
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
    log.info("Progress notes table {}: updating {}".format(
        repr(table.name), repr(CRATE_COL_LAST_NOTE)))
    execute(engine, """
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

    # Create a view, if we're on an RCEP database
    if progargs.rcep and progargs.cpft:
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
        create_view(engine, VIEW_RCEP_CPFT_PROGRESS_NOTES_CURRENT, select_sql)


def drop_for_progress_notes(table: Table, engine: Engine) -> None:
    drop_view(engine, VIEW_RCEP_CPFT_PROGRESS_NOTES_CURRENT)
    drop_indexes(engine, table, [CRATE_IDX_RIONUM_NOTENUM,
                                 CRATE_IDX_MAX_SUBNUM,
                                 CRATE_IDX_LAST_NOTE])
    drop_columns(engine, table, [CRATE_COL_MAX_SUBNUM,
                                 CRATE_COL_LAST_NOTE])


def process_clindocs_table(table: Table, engine: Engine, progargs: Any) -> None:
    # For RiO only, not RCEP
    crate_col_max_docver = Column(CRATE_COL_MAX_DOCVER, Integer, nullable=True)
    crate_col_last_doc = Column(CRATE_COL_LAST_DOC, Integer, nullable=True)
    table.append_column(crate_col_max_docver)
    table.append_column(crate_col_last_doc)
    add_columns(engine, table, [crate_col_max_docver, crate_col_last_doc])
    add_indexes(engine, table, [
        {
            'index_name': CRATE_IDX_RIONUM_SERIALNUM,
            'column': '{rio_number}, SerialNumber'.format(
                rio_number=CRATE_COL_RIO_NUMBER),
        },
        {
            'index_name': CRATE_IDX_MAX_DOCVER,
            'column': CRATE_COL_MAX_DOCVER,
        },
        {
            'index_name': CRATE_IDX_LAST_DOC,
            'column': CRATE_COL_LAST_DOC,
        },
    ])

    required_cols = ["SerialNumber", "RevisionID"]
    if not progargs.print:
        required_cols.extend([CRATE_COL_MAX_DOCVER,
                              CRATE_COL_LAST_DOC,
                              CRATE_COL_RIO_NUMBER])
    ensure_columns_present(engine, tablename=table.name,
                           column_names=required_cols)

    # Find the maximum SerialNumber for each note, and store it.
    # Slow query, even with index.
    log.info("Clinical documents table {}: updating {}".format(
        repr(table.name), repr(CRATE_COL_MAX_DOCVER)))
    execute(engine, """
        UPDATE p1
        SET p1.{max_docver_col} = subq.max_docver
        FROM {tablename} p1 JOIN (
            SELECT {rio_number}, SerialNumber, MAX(RevisionID) AS max_docver
            FROM {tablename} p2
            GROUP BY {rio_number}, SerialNumber
        ) subq
        ON subq.{rio_number} = p1.{rio_number}
        AND subq.SerialNumber = p1.SerialNumber
        WHERE p1.{max_docver_col} IS NULL
    """.format(
        max_docver_col=CRATE_COL_MAX_DOCVER,
        tablename=table.name,
        rio_number=CRATE_COL_RIO_NUMBER,
    ))

    # Set a single column accordingly
    log.info("Clinical documents table {}: updating {}".format(
        repr(table.name), repr(CRATE_COL_LAST_DOC)))
    execute(engine, """
        UPDATE {tablename} SET
            {last_doc_col} =
                CASE
                    WHEN RevisionID = {max_docver_col} THEN 1
                    ELSE 0
                END
        WHERE {last_doc_col} IS NULL
    """.format(
        tablename=table.name,
        last_doc_col=CRATE_COL_LAST_DOC,
        max_docver_col=CRATE_COL_MAX_DOCVER,
    ))


def drop_for_clindocs_table(table: Table, engine: Engine) -> None:
    drop_indexes(engine, table, [CRATE_IDX_RIONUM_SERIALNUM,
                                 CRATE_IDX_MAX_DOCVER,
                                 CRATE_IDX_LAST_DOC])
    drop_columns(engine, table, [CRATE_COL_MAX_DOCVER,
                                 CRATE_COL_LAST_DOC])


# =============================================================================
# RiO views
# =============================================================================

def get_rio_views(engine: Engine,
                  progargs: None,
                  ddhint: DDHint,
                  suppress_basetables: bool = True,
                  suppress_lookup: bool = True) -> List[ViewMaker]:
    # ddhint modified
    views = []  # type: List[ViewMaker]
    all_tables_lower = get_table_names(engine, to_lower=True)
    all_views_lower = get_view_names(engine, to_lower=True)
    all_selectables_lower = list(set(all_tables_lower + all_views_lower))
    for viewname, viewdetails in RIO_VIEWS.items():
        basetable = viewdetails['basetable']
        if basetable.lower() not in all_selectables_lower:
            log.warning("Skipping view {} as base table/view {} not "
                        "present".format(viewname, basetable))
            continue
        suppress_basetable = viewdetails.get('suppress_basetable',
                                             suppress_basetables)
        suppress_other_tables = viewdetails.get('suppress_other_tables', [])
        if suppress_basetable:
            ddhint.suppress_table(basetable)
        ddhint.suppress_tables(suppress_other_tables)
        rename = viewdetails.get('rename', None)
        enforce_same_n_rows_as_base = viewdetails.get(
            'enforce_same_n_rows_as_base', True)
        # noinspection PyTypeChecker
        viewmaker = ViewMaker(
            viewname=viewname,
            engine=engine, basetable=basetable,
            rename=rename, progargs=progargs,
            enforce_same_n_rows_as_base=enforce_same_n_rows_as_base)
        if 'add' in viewdetails:
            for addition in viewdetails['add']:
                func = addition['function']
                kwargs = addition.get('kwargs', {})
                kwargs['viewmaker'] = viewmaker
                func(**kwargs)  # will alter viewmaker
        if progargs.audit_info:
            rio_add_audit_info(viewmaker)  # will alter viewmaker
        if suppress_lookup:
            ddhint.suppress_tables(viewmaker.get_lookup_tables())
        ddhint.add_bulk_source_index_request(
            viewmaker.get_index_request_dict())
        views.append(viewmaker)
    return views


def create_rio_views(engine: Engine,
                     metadata: MetaData,
                     progargs: Any,
                     ddhint: DDHint) -> None:  # ddhint modified
    rio_views = get_rio_views(engine, progargs, ddhint)
    for viewmaker in rio_views:
        viewmaker.create_view(engine)
    ddhint.add_indexes(engine, metadata)


def drop_rio_views(engine: Engine,
                   metadata: MetaData,
                   progargs: Any,
                   ddhint: DDHint) -> None:  # ddhint modified
    rio_views = get_rio_views(engine, progargs, ddhint)
    ddhint.drop_indexes(engine, metadata)
    for viewmaker in rio_views:
        viewmaker.drop_view(engine)


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
        description=
        r"""
*   Alters a RiO database to be suitable for CRATE.

*   By default, this treats the source database as being a copy of a RiO
    database (slightly later than version 6.2; exact version unclear).
    Use the "--rcep" (+/- "--cpft") switch(es) to treat it as a
    Servelec RiO CRIS Extract Program (RCEP) v2 output database.
    """)  # noqa
    parser.add_argument("--url", required=True, help="SQLAlchemy database URL")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose")
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
        "--drop-danger-drop", action="store_true",
        help="REMOVES new columns and indexes, rather than creating them. "
             "(There's not very much danger; no real information is lost, but "
             "it might take a while to recalculate it.)")
    parser.add_argument(
        "--cpft", action="store_true",
        help="Apply hacks for Cambridgeshire & Peterborough NHS Foundation "
             "Trust (CPFT) RCEP database. Only appicable with --rcep")

    parser.add_argument(
        "--debug-skiptables", action="store_true",
        help="DEBUG-ONLY OPTION. Skip tables (view creation only)")

    prog_curr_group = parser.add_mutually_exclusive_group()
    prog_curr_group.add_argument(
        "--prognotes-current-only",
        dest="prognotes_current_only",
        action="store_true",
        help="Progress_Notes view restricted to current versions only "
             "(* default)")
    prog_curr_group.add_argument(
        "--prognotes-all",
        dest="prognotes_current_only",
        action="store_false",
        help="Progress_Notes view shows old versions too")
    parser.set_defaults(prognotes_current_only=True)

    clindocs_curr_group = parser.add_mutually_exclusive_group()
    clindocs_curr_group.add_argument(
        "--clindocs-current-only",
        dest="clindocs_current_only",
        action="store_true",
        help="Clinical_Documents view restricted to current versions only (*)")
    clindocs_curr_group.add_argument(
        "--clindocs-all",
        dest="clindocs_current_only",
        action="store_false",
        help="Clinical_Documents view shows old versions too")
    parser.set_defaults(clindocs_current_only=True)

    allerg_curr_group = parser.add_mutually_exclusive_group()
    allerg_curr_group.add_argument(
        "--allergies-current-only",
        dest="allergies_current_only",
        action="store_true",
        help="Client_Allergies view restricted to current info only")
    allerg_curr_group.add_argument(
        "--allergies-all",
        dest="allergies_current_only",
        action="store_false",
        help="Client_Allergies view shows deleted allergies too (*)")
    parser.set_defaults(allergies_current_only=False)

    audit_group = parser.add_mutually_exclusive_group()
    audit_group.add_argument(
        "--audit-info",
        dest="audit_info",
        action="store_true",
        help="Audit information (creation/update times) added to views")
    audit_group.add_argument(
        "--no-audit-info",
        dest="audit_info",
        action="store_false",
        help="No audit information added (*)")
    parser.set_defaults(audit_info=False)

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

    progargs.rio = not progargs.rcep
    if progargs.rcep:
        # RCEP
        progargs.master_patient_table = RCEP_TABLE_MASTER_PATIENT
        if progargs.cpft:
            progargs.full_prognotes_table = CPFT_RCEP_TABLE_FULL_PROGRESS_NOTES
            # We (CPFT) may have a hacked-in copy of the RiO main progress
            # notes table added to the RCEP output database.
        else:
            progargs.full_prognotes_table = None
            # The RCEP does not export sufficient information to distinguish
            # current and non-current versions of progress notes.
    else:
        # RiO
        progargs.master_patient_table = RIO_TABLE_MASTER_PATIENT
        progargs.full_prognotes_table = RIO_TABLE_PROGRESS_NOTES

    log.info("CRATE in-place preprocessor for RiO or RiO CRIS Extract Program "
             "(RCEP) databases")
    safeargs = {k: v for k, v in vars(progargs).items() if k != 'url'}
    log.debug("args (except url): {}".format(repr(safeargs)))
    log.info("RiO mode" if progargs.rio else "RCEP mode")

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
        if progargs.rio:
            drop_rio_views(engine, metadata, progargs, ddhint)
        drop_view(engine, VIEW_ADDRESS_WITH_GEOGRAPHY)
        if not progargs.debug_skiptables:
            process_all_tables(engine, metadata, progargs)
    else:
        # Tables first, then views
        if not progargs.debug_skiptables:
            process_all_tables(engine, metadata, progargs)
        if progargs.postcodedb:
            add_postcode_geography_view(engine, progargs, ddhint)
        if progargs.rio:
            create_rio_views(engine, metadata, progargs, ddhint)

    if progargs.settings_filename:
        with open(progargs.settings_filename, 'w') as f:
            print(get_rio_dd_settings(ddhint), file=f)


if __name__ == '__main__':
    pdb_run(main)
