#!/usr/bin/env python

"""
crate_anon/anonymise/anonymise.py

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

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

**Anonymise one or more SQL-based source databases into a destination database
using a data dictionary.**

"""

# =============================================================================
# Imports
# =============================================================================

import logging
import random
import sys
from datetime import datetime
from typing import Any, Dict, Iterable, Generator, List, Tuple, Union

from cardinal_pythonlib.datetimefunc import get_now_utc_pendulum
from cardinal_pythonlib.sqlalchemy.core_query import count_star, exists_plain
from cardinal_pythonlib.sqlalchemy.schema import (
    add_index,
    get_column_names,
)
from sortedcontainers import SortedSet
from sqlalchemy.schema import Column, Index, MetaData, Table
from sqlalchemy.sql import column, func, or_, select, table, text

from crate_anon.anonymise.config_singleton import config
from crate_anon.anonymise.constants import (
    BIGSEP,
    DEFAULT_CHUNKSIZE,
    DEFAULT_REPORT_EVERY,
    INDEX,
    TABLE_KWARGS,
    SEP,
)
from crate_anon.anonymise.models import (
    OptOutMpid,
    OptOutPid,
    PatientInfo,
    TridRecord,
)
from crate_anon.anonymise.patient import Patient
from crate_anon.anonymise.ddr import DataDictionaryRow
from crate_anon.common.file_io import (
    gen_integers_from_file,
    gen_words_from_file,
)
from crate_anon.common.formatting import print_record_counts
from crate_anon.common.parallel import is_my_job_by_hash, is_my_job_by_int
from crate_anon.common.sql import matches_tabledef

log = logging.getLogger(__name__)


# =============================================================================
# Database queries
# =============================================================================

def identical_record_exists_by_hash(dest_table: str,
                                    pkfield: str,
                                    pkvalue: int,
                                    hashvalue: str) -> bool:
    """
    For a given PK in a given destination table, is there a record with the
    specified value for its source hash?

    Args:
        dest_table: name of the destination table
        pkfield: name of the primary key (PK) column in the destination table
        pkvalue: integer value of the PK in the destination table
        hashvalue: hash of the source
    """
    return exists_plain(config.destdb.session,
                        dest_table,
                        column(pkfield) == pkvalue,
                        column(config.source_hash_fieldname) == hashvalue)


def identical_record_exists_by_pk(dest_table: str,
                                  pkfield: str,
                                  pkvalue: int) -> bool:
    """
    For a given PK in a given destination table, does a record exist?

    Args:
        dest_table: name of the destination table
        pkfield: name of the primary key (PK) column in the destination table
        pkvalue: integer value of the PK in the destination table
    """
    return exists_plain(config.destdb.session,
                        dest_table,
                        column(pkfield) == pkvalue)


# =============================================================================
# Database actions
# =============================================================================

def wipe_and_recreate_destination_db(incremental: bool = False) -> None:
    """
    Drop and recreate all destination tables (as specified in the DD) in the
    destination database.

    Args:
        incremental: don't drop the tables first
    """
    log.info(f"Rebuilding destination database (incremental={incremental})")
    engine = config.destdb.engine
    for tablename in config.dd.get_dest_tables():
        sqla_table = config.dd.get_dest_sqla_table(tablename,
                                                   config.timefield)
        # Drop
        if not incremental:
            log.info(f"dropping table {tablename}")
            sqla_table.drop(engine, checkfirst=True)
        # Create
        log.info(f"creating table {tablename}")
        log.debug(repr(sqla_table))
        sqla_table.create(engine, checkfirst=True)
        # Check
        resulting_fieldnames = get_column_names(engine, tablename)
        target_set = set(sqla_table.columns.keys())
        outcome_set = set(resulting_fieldnames)
        missing = list(target_set - outcome_set)
        extra = list(outcome_set - target_set)
        if missing:
            raise Exception(
                f"Missing fields in destination table {tablename}: {missing}")
        if extra:
            log.warning(
                f"Extra fields in destination table {tablename}: {extra}")


def delete_dest_rows_with_no_src_row(
        srcdbname: str,
        src_table: str,
        report_every: int = DEFAULT_REPORT_EVERY,
        chunksize: int = DEFAULT_CHUNKSIZE) -> None:
    """
    For a given source database/table, delete any rows in the corresponding
    destination table where there is no corresponding source row.

    - Can't do this in a single SQL command, since the engine can't
      necessarily see both databases.
    - Can't do this in a multiprocess way, because we're trying to do a
      ``DELETE WHERE NOT IN``.
    - However, we can get stupidly long query lists if we try to ``SELECT`` all
      the values and use a ``DELETE FROM x WHERE y NOT IN (v1, v2, v3, ...)``
      query. This crashes the MySQL connection, etc.
    - Therefore, we need a temporary table in the destination.

    Args:
        srcdbname: name (as per the data dictionary) of the source database
        src_table: name of the source table
        report_every: report to the Python log every *n* records
        chunksize: insert records every *n* records
    """
    if not config.dd.has_active_destination(srcdbname, src_table):
        return
    dest_table_name = config.dd.get_dest_table_for_src_db_table(srcdbname,
                                                                src_table)
    start = (
        f"delete_dest_rows_with_no_src_row: "
        f"{srcdbname}.{src_table} -> {config.destdb.name}.{dest_table_name}: "
    )
    log.info(start + "[WARNING: MAY BE SLOW]")

    metadata = MetaData()  # operate in isolation!
    destengine = config.destdb.engine
    destsession = config.destdb.session
    dest_table = config.dd.get_dest_sqla_table(dest_table_name,
                                               config.timefield)
    pkddr = config.dd.get_pk_ddr(srcdbname, src_table)

    # If there's no source PK, we just delete everything
    if not pkddr:
        log.info("... No source PK; deleting everything")
        destsession.execute(dest_table.delete())
        commit_destdb()
        return

    if pkddr.addition_only:
        log.info("... Table marked as addition-only; not deleting anything")
        return

    # Drop/create temporary table
    pkfield = 'srcpk'
    temptable = Table(
        config.temporary_tablename,
        metadata,
        Column(pkfield, pkddr.get_dest_sqla_coltype(), primary_key=True),
        **TABLE_KWARGS
    )
    # THIS (ABOVE) IS WHAT CONSTRAINS A USER-DEFINED PK TO BE UNIQUE WITHIN ITS
    # TABLE.
    log.debug("... dropping temporary table")
    temptable.drop(destengine, checkfirst=True)
    log.debug("... making temporary table")
    temptable.create(destengine, checkfirst=True)

    # Populate temporary table, +/- PK translation
    n = count_star(config.sources[srcdbname].session, src_table)
    log.debug(f"... populating temporary table: {n} records to go")

    def insert(records_):
        log.debug(start + f"... inserting {len(records_)} records")
        destsession.execute(temptable.insert(), records_)

    i = 0
    records = []  # type: List[Dict[str: Any]]
    for pk in gen_pks(srcdbname, src_table, pkddr.src_field):
        i += 1
        if report_every and i % report_every == 0:
            log.debug(start + f"... src row# {i} / {n}")
        if pkddr.primary_pid:
            pk = config.encrypt_primary_pid(pk)
        elif pkddr.master_pid:
            pk = config.encrypt_master_pid(pk)
        records.append({pkfield: pk})
        if i % chunksize == 0:
            insert(records)
            records = []  # type: List[Dict[str: Any]]
    if records:  # remainder
        insert(records)
    commit_destdb()

    # 4. Index -- no, hang on, it's a primary key already
    #
    # log.debug("... creating index on temporary table")
    # index = Index('_temptable_idx', temptable.columns[pkfield])
    # index.create(destengine)

    # 5. DELETE FROM desttable
    #    WHERE destpk NOT IN (SELECT srcpk FROM temptable)
    log.debug("... deleting from destination where appropriate")
    query = dest_table.delete().where(
        ~column(pkddr.dest_field).in_(
            select([temptable.columns[pkfield]])
        )
    )
    destengine.execute(query)
    commit_destdb()

    # 6. Drop temporary table
    log.debug("... dropping temporary table")
    temptable.drop(destengine, checkfirst=True)

    # 7. Commit
    commit_destdb()


def commit_destdb() -> None:
    """
    Execute a ``COMMIT`` on the destination database, and reset row counts.
    """
    config.commit_dest_db()


def commit_admindb() -> None:
    """
    Execute a ``COMMIT`` on the admin database, which is using ORM sessions.
    """
    config.admindb.session.commit()


# =============================================================================
# Opt-out
# =============================================================================

def opting_out_pid(pid: Union[int, str]) -> bool:
    """
    Does this patient wish to opt out?

    Args:
        pid: patient identifier (PID)
    """
    if pid is None:
        return False
    return OptOutPid.opting_out(config.admindb.session, pid)


def opting_out_mpid(mpid: Union[int, str]) -> bool:
    """
    Does this patient wish to opt out?

    Args:
        mpid: master patient identifier (MPID)
    """
    if mpid is None:
        return False
    return OptOutMpid.opting_out(config.admindb.session, mpid)


def gen_optout_rids() -> Generator[str, None, None]:
    """
    Generates RIDs for patients who opt out (which we can use to wipe their
    information from the destination database).

    Yields:
        string: research ID (RID)
    """
    session = config.admindb.session
    result = (
        session.query(PatientInfo.rid).
        filter(
            or_(
                PatientInfo.pid.in_(session.query(OptOutPid.pid)),
                PatientInfo.mpid.in_(session.query(OptOutMpid.mpid))
            )
        )
    )
    for row in result:
        yield row[0]


# =============================================================================
# Functions for getting PIDs from restricted set
# =============================================================================

def get_valid_pid_subset(given_pids: List[Any]) -> List[str]:
    """
    Takes a list of PIDs and returns those in the list which are also in the
    database.
    """
    pid_is_integer = config.pidtype_is_integer
    if pid_is_integer:
        # Remove non-integer values of pid if pids are supposed to be integer
        final_given_pids = []
        for pid in given_pids:
            try:
                int(pid)
                final_given_pids.append(pid)
            except (TypeError, ValueError):
                print(f"pid '{pid}' should be in integer form. ", end="")
                print("Excluding value.")
    else:
        final_given_pids = given_pids

    pids = []
    for ddr in config.dd.rows:
        if not ddr.defines_primary_pids:
            continue
        pidcol = column(ddr.src_field)
        session = config.sources[ddr.src_db].session
        query = (
            select([pidcol]).
            select_from(table(ddr.src_table)).
            where(pidcol is not None).
            distinct()
        )
        result = session.execute(query)
        real_pids = [str(x[0]) for x in result]
        for pid in real_pids:
            if pid in final_given_pids:
                pids.append(pid)

    return pids


def get_pid_subset_from_field(field: str,
                              values_to_find: List[Any]) -> List[Any]:
    """
    Takes a field name and elements from that field (values present in that
    field) and queries the database to find the PIDs associated with these
    values.

    Args:
        field: field name in the format ``database.table.field``
        values_to_find: values to look for

    Returns:
        list of PIDs

    For example, suppose you have a source table called
    ``mydb.mystudyinfo`` like this:

        =============== ============================
        pid (INTEGER)   include_in_extract (VARCHAR)
        =============== ============================
        1               no
        2               0
        3               yes
        4               1
        5               definitely
        =============== ============================

    then a call like

    .. code-block:: python

        get_subset_from_field("mydb.mystudyinfo.include_in_extract",
                              ["yes", "1", "definitely"])

    should return ``[3, 4, 5]``, assuming that ``pid`` has been correctly
    marked as the PID column in the data dictionary.

    """
    pids = []

    # Get database, table and field from 'field'
    db_parts = field.split(".")
    assert len(db_parts) == 3, (
        "field parameter must be of the form 'db.table.field'")
    db, tablename, fieldname = db_parts

    try:
        session = config.sources[db].session
    except (KeyError, AttributeError):
        print(
            f"Unable to connect to database {db}. "
            f"Remember argument to '--restrict' must be of the form "
            f"'database.table.field', or be 'pid'.")
        return pids

    fieldcol = column(fieldname)
    row = None  # for type checker
    for ddr in config.dd.rows:
        if ddr.src_db != db or not ddr.defines_primary_pids:
            continue
        # Check if the field given is in the table with the pids
        if fieldname in config.dd.get_fieldnames_for_src_table(db,
                                                               ddr.src_table):
            pidcol = column(ddr.src_field)
            session = config.sources[ddr.src_db].session
            # Find pids corresponding to the given values of specified field
            query = (
                select([pidcol]).
                select_from(table(ddr.src_table)).
                where((fieldcol.in_(values_to_find)) & (pidcol is not None)).
                distinct()
            )
            result = session.execute(query)
            pids.extend([x[0] for x in result])
            # As there is only one relavant database here, we return pids
            return pids
        # Mark out row of dd with primary pid for relavant database
        row = ddr
    if row is None:
        # Didn't find one
        return []

    # ###### Doesn't work! Trying in plain SQL #########
    # # Deal with case where the field specified isn't in the table
    # # with the primary pid
    # session = config.sources[db].session
    # pidcol = column(row.src_field)
    # session = config.sources[ddr.src_db].session
    # chosen_table = table(tablename)
    # ddr_table = table(row.src_table)
    # join_obj = ddr_table.join(chosen_table,
    #                           chosen_table.c.fieldcol == ddr_table.c.pidcol)
    # query = (
    #     select([pidcol]).
    #     select_from(join_obj).
    #     where((chosen_table.fieldcol.in_(field_elements)) &
    #                (ddr_table.pidcol is not None)).
    #     distinct()
    # )

    # # Deal with case where the field specified isn't in the table
    # # with the primary pid
    source_field = row.src_field
    source_table = row.src_table
    # Convert list to string in correct form for query
    txt_elements = ", ".join(values_to_find)
    txt_elements = "(" + txt_elements + ")"

    txt = f"SELECT {source_table}.{source_field} FROM {source_table} "
    txt += f"JOIN {tablename} ON {source_table}.{source_field}={tablename}.{fieldname} "  # noqa
    txt += f"WHERE {tablename}.{fieldname} IN {txt_elements}"
    txt += f"AND {source_table}.{source_field} IS NOT NULL"
    sql = text(txt)

    result = session.execute(sql)
    pids.extend([x[0] for x in result])

    return pids


def fieldname_is_pid(field: str) -> bool:
    """
    Checks if a field name is the literal ``'pid'`` or, if in the form
    ``'database.table.field'``, is the name of a primary PID field in the
    source database. If either of those conditions is met, return ``True``;
    otherwise, ``False``.
    """
    if field == 'pid':
        return True
    for ddr in config.dd.rows:
        if ddr.defines_primary_pids:
            if field == ddr.get_signature():
                return True
    return False


def get_pids_from_file(field: str, filename: str) -> List[str]:
    """
    Takes a field name, and a filename of values of that field, and returns
    a list of PIDs associated with them.

    Args:
        field:
            a fieldname of the format ``database.table.field``, or the literal
            ``pid``
        filename:
            A file containing words that represent values to look for, as
            follows.

            - If ``field`` is the string literal ``'pid'``, or is the name of
              a source database field containing PIDs, then the values in the
              file should be PIDs. We check that they are valid.
            - If it's another kind of field, look for values (from the file)
              in this field, and return the value of the PID column from the
              same row of the table. (See :func:`get_pid_subset_from_field`.)

    Returns:
        list of PIDs
    """
    field_is_pid = fieldname_is_pid(field)
    # pid_is_integer = config.pidtype_is_integer
    if field_is_pid:
        # If the chosen field is a PID field, just make sure all PIDs in the
        # file are valid
        given_pids = list(gen_words_from_file(filename))
        pids = get_valid_pid_subset(given_pids)
    else:
        field_elements = list(gen_words_from_file(filename))
        pids = get_pid_subset_from_field(field, field_elements)

    return pids


def get_pids_from_list(field: str, values: List[Any]) -> List[str]:
    """
    Takes a field name and a list of values, and returns a list of PIDs
    associated with them.

    Args:
        field:
            a fieldname of the format ``database.table.field``, or the literal
            ``pid``
        values:
            Values to look for, as follows.

            - If ``field`` is the string literal ``'pid'``, or is the name of
              a source database field containing PIDs, then the values in the
              should be PIDs. We check that they are valid.
            - If it's another kind of field, look for the values in this field,
              and return the value of the PID column from the same row of the
              table. (See :func:`get_pid_subset_from_field`.)

    Returns:
        list of PIDs

    """
    field_is_pid = fieldname_is_pid(field)
    if field_is_pid:
        pids = get_valid_pid_subset(values)
    else:
        pids = get_pid_subset_from_field(field, values)

    return pids


def get_pids_from_limits(low: int, high: int) -> List[Any]:
    """
    Finds PIDs from the source database that are between ``low`` and ``high``
    inclusive.

    - The SQL ``BETWEEN`` operator is inclusive
      (https://www.w3schools.com/sql/sql_between.asp).

    Args:
        low: lower (inclusive) limit
        high: upper (inclusive) limit

    Returns:
        list of PIDs in this range
    """
    pids = []
    for ddr in config.dd.rows:
        if not ddr.defines_primary_pids:
            continue
        pidcol = column(ddr.src_field)
        session = config.sources[ddr.src_db].session
        query = (
            select([pidcol]).
            select_from(table(ddr.src_table)).
            where((pidcol.between(low, high)) & (pidcol is not None)).
            distinct()
        )
        result = session.execute(query)
        pids.extend([x[0] for x in result])

    return pids


def get_pids_query_field_limits(field: str, low: int, high: int) -> List[Any]:
    """
    Takes a field name and queries the database to find the PIDs associated
    with records where ``field`` is in the range ``low`` to ``high`` inclusive.

    Args:
        field: field name in the format ``database.table.field``
        low: lower (inclusive) limit
        high: upper (inclusive) limit

    Returns:
        list of PIDs

    For example, suppose you have a source table called ``mydb.myoptouts`` like
    this:

        =============== ==========================
        pid (INTEGER)   opt_out_level (INTEGER)
        =============== ==========================
        1               0
        2               1
        3               2
        4               3
        5               4
        =============== ==========================

    then a call like

    .. code-block:: python

        get_subset_from_field("mydb.myoptouts.opt_out_level", 2, 3)

    should return ``[3, 4]``, assuming that ``pid`` has been correctly marked
    as the PID column in the data dictionary.
    """
    pids = []
    # Get database, table and field from 'field'
    db_parts = field.split(".")
    assert len(db_parts) == 3, (
        "field parameter must be of the form 'db.table.field'")
    db, tablename, fieldname = db_parts

    try:
        session = config.sources[db].session
    except (KeyError, AttributeError):
        print(
            f"Unable to connect to database {db}. "
            f"Remember argument to '--restrict' must be of the form "
            f"'database.table.field', or be 'pid'.")
        return pids

    fieldcol = column(fieldname)
    row = None
    for ddr in config.dd.rows:
        if ddr.src_db != db or not ddr.defines_primary_pids:
            continue
        # Check if the field given is in the table with the pids
        if fieldname in config.dd.get_fieldnames_for_src_table(ddr.src_db,
                                                               ddr.src_table):
            pidcol = column(ddr.src_field)
            session = config.sources[ddr.src_db].session
            # Find pids corresponding to the given values of specified field
            query = (
                select([pidcol]).
                select_from(table(ddr.src_table)).
                where((fieldcol.between(low, high)) & (pidcol is not None)).
                distinct()
            )
            result = session.execute(query)
            pids.extend([x[0] for x in result])
            # As there is only one relavant database here, we return pids
            return pids
        # Mark out row of dd with primary pid for relavant database
        row = ddr
    if row is None:
        # Didn't find one
        return []

    # Deal with case where the field specified isn't in the table
    # with the primary pid
    source_field = row.src_field
    source_table = row.src_table
    txt = f"SELECT {source_table}.{source_field} FROM {source_table} "
    txt += f"JOIN {tablename} ON {source_table}.{source_field}={tablename}.{fieldname} "  # noqa
    txt += f"WHERE ({tablename}.{fieldname} BETWEEN {low} AND {high}) "
    txt += f"AND {source_table}.{source_field} IS NOT NULL"
    sql = text(txt)

    result = session.execute(sql)
    pids.extend([x[0] for x in result])

    return pids


def get_pids_from_field_limits(field: str, low: int, high: int) -> List[Any]:
    """
    Takes a field name and a lower/upper limit, and returns a list of
    associated PIDs.

    Args:
        field:
            a fieldname of the format ``database.table.field``, or the literal
            ``pid``
        low:
            lower (inclusive) limit
        high:
            upper (inclusive) limit

    The range is used as follows.

    - If ``field`` is the string literal ``'pid'``, or is the name of
      a source database field containing PIDs, then fetch PIDs in the specified
      range and check that they are valid.
    - If it's another kind of field, look for rows where this field is in the
      specified range, and return the value of the PID column from the same row
      of the table. (See :func:`get_pids_query_field_limits`.)

    Returns:
        list of PIDs

    """
    field_is_pid = fieldname_is_pid(field)
    if field_is_pid:
        pids = get_pids_from_limits(low, high)
    else:
        pids = get_pids_query_field_limits(field, low, high)

    return pids


# =============================================================================
# Generators. Anything reading the main database should use a generator, so the
# script can scale to databases of arbitrary size.
# =============================================================================

def gen_patient_ids(
        tasknum: int = 0,
        ntasks: int = 1,
        specified_pids: List[Any] = None) -> Generator[int, None, None]:
    """
    Generate patient IDs.

    Args:
        tasknum: task number of this process (for dividing up work)
        ntasks: total number of processes (for dividing up work)
        specified_pids: optional list of PIDs to restrict ourselves to

    Yields:
        integer patient IDs (PIDs)

    - Assigns work to threads/processes, via the simple expedient of processing
      only those patient ID numbers where ``patientnum % ntasks == tasknum``.
    """

    assert ntasks >= 1
    assert 0 <= tasknum < ntasks

    pid_is_integer = config.pidtype_is_integer
    distribute_by_hash = ntasks > 1 and not pid_is_integer

    # If we're going to define based on >1 table, we need to keep track of
    # what we've processed. However, if we only have one table, we don't.
    # We can't use the mapping table easily (*), because it leads to thread/
    # process locking for database access. So we use a set.
    # (*) if not patient_id_exists_in_mapping_db(admindb, patient_id): ...

    # Debug option?
    if config.debug_pid_list:
        log.warning("USING MANUALLY SPECIFIED INTEGER PATIENT ID LIST")
        for pid in config.debug_pid_list:
            if pid_is_integer:
                if is_my_job_by_int(int(pid), tasknum=tasknum, ntasks=ntasks):
                    yield pid
            else:
                if is_my_job_by_hash(pid, tasknum=tasknum, ntasks=ntasks):
                    yield pid
        return

    # Subset specified?
    if specified_pids is not None:
        for i, pid in enumerate(specified_pids):
            if i % ntasks == tasknum:
                yield pid
        return

    # Otherwise do it properly:
    keeping_track = config.dd.n_definers > 1
    processed_ids = set()  # used only if keeping_track is True
    # ... POTENTIAL FOR MEMORY PROBLEM WITH V. BIG DB
    # ... if we ever get near that limit (for a huge number of *patients*,
    # which is much less likely than a huge number of other records), we'd
    # need to generate the IDs and stash them in a temporary table, then
    # work through that. However, a few million patients should be fine
    # for a Python set on realistic computers.
    n_found = 0
    debuglimit = config.debug_max_n_patients
    for ddr in config.dd.rows:
        if not ddr.defines_primary_pids:
            continue
        pidcol = column(ddr.src_field)
        session = config.sources[ddr.src_db].session
        query = (
            select([pidcol]).
            select_from(table(ddr.src_table)).
            where(pidcol is not None).
            distinct()
            # order_by(pidcol)  # no need to order by
        )
        if ntasks > 1 and pid_is_integer:
            query = query.where(pidcol % ntasks == tasknum)
        result = session.execute(query)
        log.debug(f"Looking for patient IDs in {ddr.src_table}.{ddr.src_field}")  # noqa
        for row in result:
            # Extract ID
            patient_id = row[0]

            # Duff?
            if patient_id is None:
                log.warning("Patient ID is NULL")
                continue

            # Operating on non-integer PIDs and not our job?
            if distribute_by_hash and not is_my_job_by_hash(
                    patient_id, tasknum=tasknum, ntasks=ntasks):
                continue

            # Duplicate?
            if keeping_track:
                # Consider, for non-integer PIDs, storing the hash64 instead
                # of the raw value.
                if patient_id in processed_ids:
                    # we've done this one already; skip it this time
                    continue
                processed_ids.add(patient_id)

            # Valid one
            log.debug(f"Found patient id: {patient_id}")
            n_found += 1
            yield patient_id

            # Too many?
            if 0 < debuglimit <= n_found:
                log.warning(
                    f"Not fetching more than {debuglimit} patients (in total "
                    f"for this process) due to debug_max_n_patients limit")
                result.close()  # http://docs.sqlalchemy.org/en/latest/core/connections.html  # noqa
                return


def estimate_count_patients() -> int:
    """
    Estimate the number of patients in the source database.

    We can't easily and quickly get the total number of patients, because they
    may be defined in multiple tables across multiple databases. We shouldn't
    fetch them all into Python in case there are billions, and it's a waste of
    effort to stash them in a temporary table and count unique rows, because
    this is all only for a progress indicator. So we approximate.
    """
    count = 0
    for ddr in config.dd.rows:
        if not ddr.defines_primary_pids:
            continue
        session = config.sources[ddr.src_db].session
        tablename = ddr.src_table
        count += count_star(session, tablename)
    return count


def gen_rows(dbname: str,
             sourcetable: str,
             sourcefields: Iterable[str],
             pid: Union[int, str] = None,
             intpkname: str = None,
             tasknum: int = 0,
             ntasks: int = 1,
             debuglimit: int = 0) -> Generator[List[Any], None, None]:
    """
    Generates rows from a source table:
    - ... each row being a list of values
    - ... each value corresponding to a field in sourcefields.
    - ... optionally restricted to a single patient

    If the table has a PK and we're operating in a multitasking situation,
    generate just the rows for this task (thread/process).

    Args:
        dbname: name (as per the data dictionary) of the source database
        sourcetable: name of the source table
        sourcefields: names of fields in the source table
        pid: patient ID (PID)
        intpkname: name of the integer PK column in the source table, if one
            exists
        tasknum: task number of this process (for dividing up work)
        ntasks: total number of processes (for dividing up work)
        debuglimit: if specified, the maximum number of rows to process

    Yields:
        lists, each representing one row and containing values for each of the
        ``sourcefields``
    """
    t = config.sources[dbname].metadata.tables[sourcetable]
    q = select([column(c) for c in sourcefields]).select_from(t)
    # not ordered

    # Restrict to one patient?
    if pid is not None:
        pidcol_name = config.dd.get_pid_name(dbname, sourcetable)
        q = q.where(column(pidcol_name) == pid)
    else:
        # For non-patient tables: divide up rows across tasks?
        if intpkname is not None and ntasks > 1:
            q = q.where(column(intpkname) % ntasks == tasknum)
            # This does not require a user-defined PK to be unique. But other
            # constraints do: see delete_dest_rows_with_no_src_row().

    db_table_tuple = (dbname, sourcetable)
    result = config.sources[dbname].session.execute(q)
    for row in result:
        if 0 < debuglimit <= config.rows_inserted_per_table[db_table_tuple]:
            if not config.warned_re_limits[db_table_tuple]:
                log.warning(
                    f"Table {dbname}.{sourcetable}: not fetching more than "
                    f"{debuglimit} rows (in total for this process) "
                    f"due to debugging limits")
                config.warned_re_limits[db_table_tuple] = True
            result.close()  # http://docs.sqlalchemy.org/en/latest/core/connections.html  # noqa
            return
        config.notify_src_bytes_read(sys.getsizeof(row))  # ... approximate!
        yield list(row)
        # yield dict(zip(row.keys(), row))
        # see also http://stackoverflow.com/questions/19406859
        config.rows_inserted_per_table[db_table_tuple] += 1


def count_rows(dbname: str,
               sourcetable: str,
               pid: Union[int, str] = None) -> int:
    """
    Count the number of rows in a table for a given PID.

    Args:
        dbname: name (as per the data dictionary) of the source database
        sourcetable: name of the source table
        pid: patient ID (PID)

    Returns:
        the number of records

    """
    # Count function to match gen_rows()
    session = config.sources[dbname].session
    query = select([func.count()]).select_from(table(sourcetable))
    if pid is not None:
        pidcol_name = config.dd.get_pid_name(dbname, sourcetable)
        query = query.where(column(pidcol_name) == pid)
    return session.execute(query).scalar()


def gen_index_row_sets_by_table(
        tasknum: int = 0,
        ntasks: int = 1) -> Generator[Tuple[str, List[DataDictionaryRow]],
                                      None, None]:
    """
    Generate ``table, list_of_dd_rows_for_indexed_fields`` tuples for all
    tables requiring indexing.

    Args:
        tasknum: task number of this process (for dividing up work)
        ntasks: total number of processes (for dividing up work)

    Yields:
        tuple: ``table, list_of_dd_rows_for_indexed_fields`` for each table
        as above

    """
    indexrows = [ddr for ddr in config.dd.rows
                 if ddr.index and not ddr.omit]
    tables = SortedSet([r.dest_table for r in indexrows])
    # must sort for parallel processing consistency: set() order varies
    for i, t in enumerate(tables):
        if i % ntasks != tasknum:
            continue
        tablerows = [r for r in indexrows if r.dest_table == t]
        yield (t, tablerows)


def gen_nonpatient_tables_without_int_pk(
        tasknum: int = 0,
        ntasks: int = 1) -> Generator[Tuple[str, str], None, None]:
    """
    Generate ``(source db name, source table)`` tuples for all tables that

    (a) don't contain patient information and
    (b) don't have an integer PK.

    Args:
        tasknum: task number of this process (for dividing up work)
        ntasks: total number of processes (for dividing up work)

    Yields:
        tuple: ``source_db_name, source_table`` for each table as above

    """
    db_table_pairs = config.dd.get_src_dbs_tables_with_no_pt_info_no_pk()
    # ... returns a SortedSet, so safe to divide parallel processing like this:
    for i, pair in enumerate(db_table_pairs):
        if i % ntasks != tasknum:
            continue
        yield pair  # will be a (dbname, table) tuple


def gen_nonpatient_tables_with_int_pk() -> Generator[Tuple[str, str, str],
                                                     None, None]:
    """
    Generate ``source_db_name, source_table, pk_name`` tuples for all tables
    that

    (a) don't contain patient information and
    (b) do have an integer PK.
    """
    db_table_pairs = config.dd.get_src_dbs_tables_with_no_pt_info_int_pk()
    for pair in db_table_pairs:
        db = pair[0]
        tablename = pair[1]
        pkname = config.dd.get_int_pk_name(db, tablename)
        yield (db, tablename, pkname)


def gen_pks(srcdbname: str,
            tablename: str,
            pkname: str) -> Generator[int, None, None]:
    """
    Generate PK values from a table.

    Args:
        srcdbname: name (as per the data dictionary) of the database
        tablename: name of the table
        pkname: name of the PK column

    Yields:
        int: each primary key
    """
    db = config.sources[srcdbname]
    t = db.metadata.tables[tablename]
    q = select([column(pkname)]).select_from(t)
    result = db.session.execute(q)
    for row in result:
        yield row[0]


# =============================================================================
# Core functions
# =============================================================================
# - For multithreaded use, the patients are divvied up across the threads.
# - KEY THREADING RULE: ALL THREADS MUST HAVE FULLY INDEPENDENT DATABASE
#   CONNECTIONS.

def process_table(sourcedbname: str,
                  sourcetable: str,
                  patient: Patient = None,
                  incremental: bool = False,
                  intpkname: str = None,
                  tasknum: int = 0,
                  ntasks: int = 1,
                  free_text_limit: int = None) -> None:
    """
    Process a table. This can either be a patient table (in which case the
    patient's scrubber is applied and only rows for that patient are processed)
    or not (in which case the table is just copied).

    Args:
        sourcedbname:
            name (as per the data dictionary) of the source database
        sourcetable:
            name of the source table
        patient:
            :class:`crate_anon.anonymise.patient.Patient` object, or ``None``
            for non-patient tables
        incremental:
            perform an incremental update, rather than a full run?
        intpkname:
            name of the integer PK column in the source table
        tasknum:
            task number of this process (for dividing up work)
        ntasks:
            total number of processes (for dividing up work)
        free_text_limit:
            If specified, any text field that contains content longer than this
            many characters will be wiped (set to ``NULL``) as it's sent to the
            destination database.
    """
    start = f"process_table: {sourcedbname}.{sourcetable}: "
    pid = None if patient is None else patient.get_pid()
    log.debug(start + f"pid={pid}, incremental={incremental}")

    # Limit the data quantity for debugging?
    srccfg = config.sources[sourcedbname].srccfg
    if matches_tabledef(sourcetable, srccfg.debug_limited_tables):
        debuglimit = srccfg.debug_row_limit
        # log.debug(f"Limiting table {sourcetable} to {debuglimit} rows "
        #           f"(per process)")
    else:
        debuglimit = 0

    ddrows = config.dd.get_rows_for_src_table(sourcedbname, sourcetable)
    if all(ddr.omit for ddr in ddrows):
        return
    addhash = any(ddr.add_src_hash for ddr in ddrows)
    addtrid = any(ddr.primary_pid and not ddr.omit for ddr in ddrows)
    constant = any(ddr.constant for ddr in ddrows)
    # If addhash or constant is true AND we are not omitting all rows, then
    # the non-omitted rows will include the source PK (by the data dictionary's
    # validation process).
    ddrows = [ddr for ddr in ddrows
              if (
                  (not ddr.omit) or  # used for data
                  (addhash and ddr.scrub_src) or  # used for hash
                  ddr.inclusion_values or  # used for filter
                  ddr.exclusion_values  # used for filter
              )]
    if not ddrows:
        # No columns to process at all.
        return
    dest_table = ddrows[0].dest_table
    sourcefields = []  # type: List[str]
    pkfield_index = None
    src_pk_name = None
    dest_pk_name = None
    for i, ddr in enumerate(ddrows):
        # log.debug(f"DD row: {str(ddr)}")
        if ddr.pk:
            pkfield_index = i
            src_pk_name = ddr.src_field
            dest_pk_name = ddr.dest_field
        sourcefields.append(ddr.src_field)
    srchash = None
    timefield = config.timefield
    sqla_table = config.dd.get_dest_sqla_table(dest_table, timefield)
    session = config.destdb.session

    # Count what we'll do, so we can give a better indication of progress
    count = count_rows(sourcedbname, sourcetable, pid)
    n = 0
    recnum = tasknum or 0

    # Process the rows
    for row in gen_rows(sourcedbname, sourcetable, sourcefields,
                        pid, debuglimit=debuglimit,
                        intpkname=intpkname, tasknum=tasknum, ntasks=ntasks):
        n += 1
        if n % config.report_every_n_rows == 0:
            log.info(
                start +
                f"processing record {recnum + 1}/{count}"
                f"{' for this patient' if pid is not None else ''} "
                f"({config.overall_progress()})")
        recnum += ntasks or 1
        if addhash:
            srchash = config.hash_object(row)
            if incremental and identical_record_exists_by_hash(
                    dest_table, dest_pk_name, row[pkfield_index], srchash):
                log.debug(
                    f"... ... skipping unchanged record (identical by hash): "
                    f"{sourcedbname}.{sourcetable}.{src_pk_name} = "
                    f"(destination) {dest_table}.{dest_pk_name} = "
                    f"{row[pkfield_index]}")
                continue
        if constant:
            if incremental and identical_record_exists_by_pk(
                    dest_table, dest_pk_name, row[pkfield_index]):
                log.debug(
                    f"... ... skipping unchanged record (identical by PK and "
                    f"marked as constant): "
                    f"{sourcedbname}.{sourcetable}.{src_pk_name} = "
                    f"(destination) {dest_table}.{dest_pk_name} = "
                    f"{row[pkfield_index]}")
                continue
        destvalues = {}
        skip_row = False
        for i, ddr in enumerate(ddrows):
            value = row[i]
            # Filter out free text over specified length
            if (free_text_limit is not None and
                    len(str(value)) > free_text_limit):
                datatype = ddr.src_datatype
                if (datatype == "TEXT" or datatype.startswith("CHAR") or
                        datatype.startswith("VARCHAR")):
                    # This is safe because no destination fields are nullable
                    # except id columns?
                    destvalues[ddr.dest_field] = None
                    continue
            if ddr.skip_row_by_value(value):
                # log.debug("skipping row based on inclusion/exclusion values")
                skip_row = True
                break  # skip row
            # NOTE: would be most efficient if ddrows were ordered with
            # inclusion/exclusion fields first. (Not yet done automatically.)
            if ddr.omit:
                continue  # skip column

            if ddr.primary_pid:
                assert(value == patient.get_pid())
                value = patient.get_rid()
            elif ddr.master_pid:
                value = config.encrypt_master_pid(value)

            for alter_method in ddr.get_alter_methods():
                value, skiprow = alter_method.alter(
                    value=value, ddr=ddr, row=row,
                    ddrows=ddrows, patient=patient)
                if skiprow:
                    break  # from alter method loop

            if skip_row:
                break  # from data dictionary row (field) loop

            destvalues[ddr.dest_field] = value

            if timefield:
                destvalues[timefield] = datetime.utcnow()

        if skip_row or not destvalues:
            continue  # next row

        if addhash:
            destvalues[config.source_hash_fieldname] = srchash
        if addtrid:
            destvalues[config.trid_fieldname] = patient.get_trid()

        q = sqla_table.insert_on_duplicate().values(destvalues)
        session.execute(q)

        # Trigger an early commit?
        config.notify_dest_db_transaction(
            n_rows=1, n_bytes=sys.getsizeof(destvalues))  # ... approximate!
        # ... quicker than e.g. len(repr(...)), as judged by a timeit() call.

    log.debug(start + f"finished: pid={pid}")
    commit_destdb()


def create_indexes(tasknum: int = 0, ntasks: int = 1) -> None:
    """
    Create indexes for the destination tables.

    Args:
        tasknum: task number of this process (for dividing up work)
        ntasks: total number of processes (for dividing up work)
    """
    log.info(SEP + "Create indexes")
    engine = config.get_destdb_engine_outside_transaction()
    mssql = engine.dialect.name == 'mssql'
    mssql_fulltext_columns_by_table = []  # type: List[List[Column]]
    for (tablename, tablerows) in gen_index_row_sets_by_table(tasknum=tasknum,
                                                              ntasks=ntasks):
        sqla_table = config.dd.get_dest_sqla_table(tablename, config.timefield)
        mssql_fulltext_columns = []  # type: List[Column]
        for tr in tablerows:
            sqla_column = sqla_table.columns[tr.dest_field]
            fulltext = (tr.index is INDEX.FULLTEXT)
            if fulltext and mssql:
                # Special processing: we can only create one full-text index
                # per table under SQL Server, but it can cover multiple
                # columns; see below
                mssql_fulltext_columns.append(sqla_column)
            else:
                add_index(engine=engine,
                          sqla_column=sqla_column,
                          unique=(tr.index is INDEX.UNIQUE),
                          fulltext=fulltext,
                          length=tr.indexlen)
            # Extra index for TRID?
            if tr.primary_pid:
                add_index(engine, sqla_table.columns[config.trid_fieldname],
                          unique=(tr.index is INDEX.UNIQUE))
        if mssql_fulltext_columns:
            mssql_fulltext_columns_by_table.append(mssql_fulltext_columns)
    # Special processing for SQL Server FULLTEXT indexes, if any:
    for multiple_sqla_columns in mssql_fulltext_columns_by_table:
        add_index(engine=engine,
                  multiple_sqla_columns=multiple_sqla_columns,
                  fulltext=True)


def patient_processing_fn(tasknum: int = 0,
                          ntasks: int = 1,
                          incremental: bool = False,
                          specified_pids: List[int] = None,
                          free_text_limit: int = None) -> None:
    """
    Main function to anonymise patient data.

    - Iterate through patient IDs;
    - build the scrubber for each patient;
    - process source data for that patient, scrubbing it;
    - insert the patient into the mapping table in the admin database.

    Args:
        tasknum: task number of this process (for dividing up work)
        ntasks: total number of processes (for dividing up work)
        incremental: perform an incremental update, rather than a full run?
        specified_pids: if specified, restrict to specific PIDs
        free_text_limit: as per :func:`process_table`
    """
    n_patients = estimate_count_patients() // ntasks
    i = 0
    for pid in gen_patient_ids(tasknum, ntasks,
                               specified_pids=specified_pids):
        # gen_patient_ids() assigns the work to the appropriate thread/process
        # Check for an abort signal once per patient processed
        i += 1
        log.info(
            f"Processing patient ID: {pid} (incremental={incremental}; "
            f"patient {i}/~{n_patients} for this process; "
            f"{config.overall_progress()})")

        # Opt out based on PID?
        if opting_out_pid(pid):
            log.info("... opt out based on PID")
            continue
        # MPID information won't be present until we scan all the fields (which
        # we do as we build the scrubber).

        # Gather scrubbing information for a patient. (Will save.)
        patient = Patient(pid)

        if patient.mandatory_scrubbers_unfulfilled:
            log.warning(
                f"Skipping patient with PID={pid} as the following scrub_src "
                f"fields are required and had no data: "
                f"{patient.mandatory_scrubbers_unfulfilled}")
            continue

        # Opt out based on MPID?
        if opting_out_mpid(patient.get_mpid()):
            log.info("... opt out based on MPID")
            continue

        patient_unchanged = patient.unchanged()
        if incremental:
            if patient_unchanged:
                log.debug("Scrubber unchanged; may save some time")
            else:
                log.debug("Scrubber new or changed; reprocessing in full")

        # For each source database/table...
        for d in config.dd.get_source_databases():
            log.debug(f"Patient {pid}, processing database: {d}")
            for t in config.dd.get_patient_src_tables_with_active_dest(d):
                log.debug(f"Patient {pid}, processing table {d}.{t}")
                process_table(d, t,
                              patient=patient,
                              incremental=(incremental and patient_unchanged),
                              free_text_limit=free_text_limit)

    commit_destdb()


def wipe_destination_data_for_opt_out_patients(report_every: int = 1000,
                                               chunksize: int = 10000) -> None:
    """
    Delete any data from patients that have opted out (after their data was
    processed on a previous occasion).

    (Slightly complicated by the fact that the destination database can't
    necessarily 'see' the mapping database, so we need to cache the RID keys in
    the destination database temporarily.)

    Args:
        report_every: report logging information every *n* records
        chunksize: insert records every *n* records
    """
    start = "wipe_opt_out_patients"
    log.info(start)

    adminsession = config.admindb.session
    metadata = MetaData()  # operate in isolation!
    destengine = config.destdb.engine
    destsession = config.destdb.session
    ridfield = config.research_id_fieldname

    # Drop/create temporary table
    pkfield = 'rid'
    temptable = Table(
        config.temporary_tablename,
        metadata,
        Column(pkfield, config.SqlTypeEncryptedPid, primary_key=True),
        **TABLE_KWARGS
    )
    log.debug(start + ": 1. dropping temporary table")
    temptable.drop(destengine, checkfirst=True)  # use engine, not session
    log.debug(start + ": 2. making temporary table")
    temptable.create(destengine, checkfirst=True)  # use engine, not session

    log.debug(start + ": 3. populating temporary table with RIDs")

    def insert(records_):
        # records_: a list of dictionaries
        # http://docs.sqlalchemy.org/en/latest/core/tutorial.html
        log.debug(start + f"... inserting {len(records_)} records")
        destsession.execute(temptable.insert(), records_)

    i = 0
    records = []  # type: List[Dict[str: Any]]
    for rid in gen_optout_rids():
        i += 1
        if report_every and i % report_every == 0:
            log.debug(start + f"... src row# {i}")
        records.append({pkfield: rid})  # a row is a dict of values
        if i % chunksize == 0:
            insert(records)
            records = []  # type: List[Dict[str: Any]]
    if records:  # remainder
        insert(records)
    commit_destdb()

    log.debug(start + ": 4. creating index on temporary table")
    index = Index('_temptable_idx', temptable.columns[pkfield])
    index.create(destengine)  # use engine, not session

    # 5. For each patient destination table,
    #    DELETE FROM desttable WHERE rid IN (SELECT rid FROM temptable)
    log.debug(start + ": 5. deleting from destination table by opt-out RID")
    for dest_table_name in config.dd.get_dest_tables_with_patient_info():
        log.debug(start + f": ... {dest_table_name}")
        dest_table = config.dd.get_dest_sqla_table(dest_table_name,
                                                   config.timefield)
        query = dest_table.delete().where(
            column(ridfield).in_(
                select([temptable.columns[pkfield]])
            )
        )
        destengine.execute(query)
        commit_destdb()

    log.debug(start + ": 6. dropping temporary table")
    temptable.drop(destengine, checkfirst=True)  # use engine, not session
    commit_destdb()

    log.debug(start + ": 7. deleting opt-out patients from mapping table")
    adminsession.query(PatientInfo).filter(
        or_(
            PatientInfo.pid.in_(adminsession.query(OptOutPid.pid)),
            PatientInfo.mpid.in_(adminsession.query(OptOutMpid.mpid))
        )
    ).delete(synchronize_session=False)
    commit_admindb()


def drop_remake(incremental: bool = False,
                skipdelete: bool = False) -> None:
    """
    Drop and rebuild (a) mapping table, (b) destination tables.

    Args:
        incremental:
            doesn't drop tables; just deletes destination information where
            source information no longer exists.
        skipdelete:
            For incremental updates, skip deletion of rows present in the
            destination but not the source
    """
    log.info(SEP + "Creating database structure +/- deleting dead data")
    engine = config.admindb.engine
    if not incremental:
        log.info("Dropping admin tables except opt-out")
        # not OptOut

        # noinspection PyUnresolvedReferences
        PatientInfo.__table__.drop(engine, checkfirst=True)
        # noinspection PyUnresolvedReferences
        TridRecord.__table__.drop(engine, checkfirst=True)
    log.info("Creating admin tables")
    # noinspection PyUnresolvedReferences
    OptOutPid.__table__.create(engine, checkfirst=True)
    # noinspection PyUnresolvedReferences
    OptOutMpid.__table__.create(engine, checkfirst=True)
    # noinspection PyUnresolvedReferences
    PatientInfo.__table__.create(engine, checkfirst=True)
    # noinspection PyUnresolvedReferences
    TridRecord.__table__.create(engine, checkfirst=True)

    wipe_and_recreate_destination_db(incremental=incremental)
    if skipdelete or not incremental:
        return
    for d in config.dd.get_source_databases():
        for t in config.dd.get_src_tables(d):
            delete_dest_rows_with_no_src_row(
                d, t, report_every=config.report_every_n_rows,
                chunksize=config.chunksize)


def gen_opt_out_pids_from_file(mpid: bool = False) \
        -> Generator[Union[int, str], None, None]:
    """
    Generate opt-out PIDs (or MPIDs) from a file.

    Args:
        mpid:
            generate MPIDs, not PIDs (and therefore use
            ``config.optout_mpid_filenames``, not
            ``config.optout_pid_filenames``, as the set of filenames to read)

    Yields:
        each PID (or MPID), which will be either ``str`` or ``int`` depending
        on the value of ``config.mpidtype_is_integer`` or
        ``config.pidtype_is_integer``.
    """
    if mpid:
        txt = "MPID"
        filenames = config.optout_mpid_filenames
        as_int = config.mpidtype_is_integer
    else:
        txt = "PID"
        filenames = config.optout_pid_filenames
        as_int = config.pidtype_is_integer
    if not filenames:
        log.info(f"... no opt-out {txt} disk files in use")
    else:
        for filename in filenames:
            log.info(f"... {txt} file: {filename}")
            if as_int:
                for pid in gen_integers_from_file(filename):
                    yield pid
            else:
                for pid in gen_words_from_file(filename):
                    yield pid


def gen_opt_out_pids_from_database(mpid: bool = False) \
        -> Generator[Any, None, None]:
    """
    Generate opt-out PIDs (or MPIDs) from a database.

    Args:
        mpid: generate MPIDs, not PIDs

    Yields:
        each PID (or MPID)

    """
    txt = "MPID" if mpid else "PID"
    found_one = False
    defining_fields = config.dd.get_optout_defining_fields()
    for t in defining_fields:
        src_db, src_table, optout_colname, pid_colname, mpid_colname = t
        id_colname = mpid_colname if mpid else pid_colname
        if not id_colname:
            continue
        found_one = True
        session = config.sources[src_db].session
        log.info(
            f"... {src_db}.{src_table}.{optout_colname} ({txt}={id_colname})")
        sqla_table = table(src_table)
        optout_defining_col = column(optout_colname)
        idcol = column(id_colname)
        query = (
            select([idcol]).
            select_from(sqla_table).
            where(optout_defining_col.in_(config.optout_col_values)).
            distinct()
        )
        # no need for an order_by clause
        result = session.execute(query)
        for row in result:
            pid = row[0]
            yield pid
    if not found_one:
        log.info(f"... no opt-out-defining {txt} fields in data dictionary")


def setup_opt_out(incremental: bool = False) -> None:
    """
    - Hunts far and wide through its sources for PID/MPID values of patients
      who wish to opt out.
    - Adds them to the admin tables for
      :class:`crate_anon.anonymise.models.OptOutPid` and
      :class:`crate_anon.anonymise.models.OptOutMpid`.

    Args:
        incremental:
            after adding opt-out patients, delete any data for them found
            in the destination database. (Unnecessary for "full" rather than
            "incremental" runs, since "full" runs delete all the destination
            tables and start again.)

    """
    log.info(SEP + "Managing opt-outs")
    adminsession = config.admindb.session

    log.info("Hunting for opt-out patients from disk file...")
    for pid in gen_opt_out_pids_from_file():
        # noinspection PyTypeChecker
        OptOutPid.add(adminsession, pid)
    for mpid in gen_opt_out_pids_from_file(mpid=True):
        # noinspection PyTypeChecker
        OptOutMpid.add(adminsession, mpid)

    log.info("Hunting for opt-out patients from database...")
    for pid in gen_opt_out_pids_from_database():
        OptOutPid.add(adminsession, pid)
    for mpid in gen_opt_out_pids_from_database(mpid=True):
        OptOutMpid.add(adminsession, mpid)

    adminsession.commit()

    if incremental:
        wipe_destination_data_for_opt_out_patients()


def process_nonpatient_tables(tasknum: int = 0,
                              ntasks: int = 1,
                              incremental: bool = False,
                              free_text_limit: int = None) -> None:
    """
    Copies all non-patient tables.

    - If they have an integer PK, the work may be parallelized.
    - If not, whole tables are assigned to different processes in parallel
      mode.

    Args:
        tasknum:
            task number of this process (for dividing up work)
        ntasks:
            total number of processes (for dividing up work)
        incremental:
            perform an incremental update, rather than a full run?
        free_text_limit:
            If specified, any text field that contains content longer than this
            many characters will be wiped (set to ``NULL``) as it's sent to the
            destination database.

    """
    log.info(SEP + "Non-patient tables: (a) with integer PK")
    for (d, t, pkname) in gen_nonpatient_tables_with_int_pk():
        log.info(
            f"Processing non-patient table {d}.{t} (PK: {pkname}) "
            f"({config.overall_progress()})...")
        # noinspection PyTypeChecker
        process_table(d, t, patient=None,
                      incremental=incremental,
                      intpkname=pkname, tasknum=tasknum, ntasks=ntasks,
                      free_text_limit=free_text_limit)
        commit_destdb()
    log.info(SEP + "Non-patient tables: (b) without integer PK")
    for (d, t) in gen_nonpatient_tables_without_int_pk(tasknum=tasknum,
                                                       ntasks=ntasks):
        log.info(
            f"Processing non-patient table {d}.{t} "
            f"({config.overall_progress()})...")
        # Force this into single-task mode, i.e. we have already parallelized
        # by assigning different tables to different processes; don't split
        # the work within a single table.
        # noinspection PyTypeChecker
        process_table(d, t, patient=None,
                      incremental=incremental,
                      intpkname=None, tasknum=0, ntasks=1,
                      free_text_limit=free_text_limit)
        commit_destdb()


def process_patient_tables(tasknum: int = 0,
                           ntasks: int = 1,
                           incremental: bool = False,
                           specified_pids: List[int] = None,
                           free_text_limit: int = None) -> None:
    """
    Process all patient tables, optionally in a parallel-processing fashion.

    All the work is done via :func:`patient_processing_fn`.

    Args:
        tasknum:
            task number of this process (for dividing up work)
        ntasks:
            total number of processes (for dividing up work)
        incremental:
            perform an incremental update, rather than a full run?
        specified_pids:
            if specified, restrict to specific PIDs
        free_text_limit:
            If specified, any text field that contains content longer than this
            many characters will be wiped (set to ``NULL``) as it's sent to the
            destination database.

    """
    # We'll use multiple destination tables, so commit right at the end.
    log.info(SEP + "Patient tables")
    if ntasks == 1:
        log.info("Single-threaded, single-process mode")
    else:
        log.info(
            f"PROCESS {tasknum} (numbered from zero) OF {ntasks} PROCESSES")
    patient_processing_fn(tasknum=tasknum, ntasks=ntasks,
                          incremental=incremental,
                          specified_pids=specified_pids,
                          free_text_limit=free_text_limit)

    if ntasks > 1:
        log.info(f"Process {tasknum}: FINISHED ANONYMISATION")
    else:
        log.info("FINISHED ANONYMISATION")

    # Commit (should be redundant)
    commit_destdb()


def show_source_counts() -> None:
    """
    Show (print to stdout) the number of records in all source tables.
    """
    print("SOURCE TABLE RECORD COUNTS:")
    counts = []  # type: List[Tuple[str, int]]
    for d in config.dd.get_source_databases():
        session = config.sources[d].session
        for t in config.dd.get_src_tables(d):
            n = count_star(session, t)
            counts.append((f"{d}.{t}", n))
    print_record_counts(counts)


def show_dest_counts() -> None:
    """
    Show (print to stout) the number of records in all destination tables.
    """
    print("DESTINATION TABLE RECORD COUNTS:")
    counts = []  # type: List[Tuple[str, int]]
    session = config.destdb.session
    for t in config.dd.get_dest_tables():
        n = count_star(session, t)
        counts.append((f"DESTINATION: {t}", n))
    print_record_counts(counts)


# =============================================================================
# Main
# =============================================================================

def anonymise(args: Any) -> None:
    """
    Main entry point for anonymisation.

    Args:
        args:
            argparse arguments, from
            :func:`crate_anon.anonymise.anonymise_cli.main`
    """
    # Validate args
    if args.nprocesses < 1:
        raise ValueError("--nprocesses must be >=1")
    if args.process < 0 or args.process >= args.nprocesses:
        raise ValueError(
            "--process argument must be from 0 to (nprocesses - 1) inclusive")
    if args.nprocesses > 1 and args.dropremake:
        raise ValueError("Can't use nprocesses > 1 with --dropremake")
    if args.incrementaldd and args.draftdd:
        raise ValueError("Can't use --incrementaldd and --draftdd")

    everything = not any([args.dropremake, args.optout, args.nonpatienttables,
                          args.patienttables, args.index])

    # Load/validate config
    config.report_every_n_rows = args.reportevery
    config.chunksize = args.chunksize
    config.debug_scrubbers = args.debugscrubbers
    config.save_scrubbers = args.savescrubbers
    config.set_echo(args.echo)
    if not args.draftdd:
        config.load_dd(check_against_source_db=not args.skip_dd_check)

    if args.draftdd or args.incrementaldd:
        # Note: the difference is that for incrementaldd, the data dictionary
        # will have been loaded from disk; for draftdd, it won't (so a
        # completely fresh one will be generated).
        config.dd.read_from_source_databases()
        print(config.dd.get_tsv())
        return

    config.check_valid()

    if args.count:
        show_source_counts()
        show_dest_counts()
        return

    pids = None
    if args.restrict:
        if args.file:
            pids = get_pids_from_file(args.restrict, args.file)
        elif args.limits:
            pids = get_pids_from_field_limits(args.restrict, args.limits[0],
                                              args.limits[1])
        elif args.list:
            pids = get_pids_from_list(args.restrict, args.list)
        else:
            raise ValueError("'--restrict' option requires one of "
                             "'--file', '--limits' or '--list'")
        if not pids:
            log.warning("No valid patient ids found for the conditions given")

    # random number seed
    random.seed(args.seed)

    # -------------------------------------------------------------------------

    log.info(BIGSEP + "Starting")
    start = get_now_utc_pendulum()

    # 1. Drop/remake tables. Single-tasking only.
    if args.dropremake or everything:
        drop_remake(incremental=args.incremental,
                    skipdelete=args.skipdelete)

    # 2. Deal with opt-outs
    if args.optout or everything:
        setup_opt_out(incremental=args.incremental)

    # 3. Tables with patient info.
    #    Process PER PATIENT, across all tables, because we have to synthesize
    #    information to scrub across the entirety of that patient's record.
    if args.patienttables or everything:
        process_patient_tables(tasknum=args.process,
                               ntasks=args.nprocesses,
                               incremental=args.incremental,
                               specified_pids=pids,
                               free_text_limit=args.filtertext)

    # 4. Tables without any patient ID (e.g. lookup tables). Process PER TABLE.
    if args.nonpatienttables or everything:
        process_nonpatient_tables(tasknum=args.process,
                                  ntasks=args.nprocesses,
                                  incremental=args.incremental,
                                  free_text_limit=args.filtertext)

    # 5. Indexes. ALWAYS FASTEST TO DO THIS LAST. Process PER TABLE.
    if args.index or everything:
        create_indexes(tasknum=args.process, ntasks=args.nprocesses)

    log.info(BIGSEP + "Finished")
    end = get_now_utc_pendulum()
    time_taken = end - start
    log.info(f"Time taken: {time_taken.total_seconds()} seconds")
    # config.dd.debug_cache_hits()
