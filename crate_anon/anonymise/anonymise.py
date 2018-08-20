#!/usr/bin/env python
# crate_anon/anonymise/anonymise.py

"""
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

Anonymise multiple SQL-based databases using a data dictionary.

"""

# =============================================================================
# Imports
# =============================================================================

import logging
import random
import sys
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
    """
    log.info("Rebuilding destination database (incremental={})".format(
        incremental))
    engine = config.destdb.engine
    for tablename in config.dd.get_dest_tables():
        sqla_table = config.dd.get_dest_sqla_table(tablename)
        # Drop
        if not incremental:
            log.info("dropping table {}".format(tablename))
            sqla_table.drop(engine, checkfirst=True)
        # Create
        log.info("creating table {}".format(tablename))
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
                "Missing fields in destination table {t}: {fields}".format(
                    t=tablename, fields=missing))
        if extra:
            log.warning(
                "Extra fields in destination table {t}: {fields}".format(
                    t=tablename, fields=extra))


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
      DELETE WHERE NOT IN.
    - However, we can get stupidly long query lists if we try to SELECT all
      the values and use a DELETE FROM x WHERE y NOT IN (v1, v2, v3, ...)
      query. This crashes the MySQL connection, etc.
    - Therefore, we need a temporary table in the destination.
    """
    if not config.dd.has_active_destination(srcdbname, src_table):
        return
    dest_table_name = config.dd.get_dest_table_for_src_db_table(srcdbname,
                                                                src_table)
    start = "delete_dest_rows_with_no_src_row: {}.{} -> {}.{}: ".format(
        srcdbname, src_table, config.destdb.name, dest_table_name)
    log.info(start + "[WARNING: MAY BE SLOW]")

    metadata = MetaData()  # operate in isolation!
    destengine = config.destdb.engine
    destsession = config.destdb.session
    dest_table = config.dd.get_dest_sqla_table(dest_table_name)
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
    log.debug("... populating temporary table: {} records to go".format(n))

    def insert(records_):
        log.debug(start + "... inserting {} records".format(len(records_)))
        destsession.execute(temptable.insert(), records_)

    i = 0
    records = []  # type: List[Dict[str: Any]]
    for pk in gen_pks(srcdbname, src_table, pkddr.src_field):
        i += 1
        if report_every and i % report_every == 0:
            log.debug(start + "... src row# {} / {}".format(i, n))
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
    Execute a COMMIT on the destination database, and reset row counts.
    """
    config.commit_dest_db()


def commit_admindb() -> None:
    """
    Execute a COMMIT on the admin database, which is using ORM sessions.
    """
    config.admindb.session.commit()


# =============================================================================
# Opt-out
# =============================================================================

def opting_out_pid(pid: Union[int, str]) -> bool:
    """Does this patient wish to opt out?"""
    if pid is None:
        return False
    return OptOutPid.opting_out(config.admindb.session, pid)


def opting_out_mpid(mpid: Union[int, str]) -> bool:
    """Does this patient wish to opt out?"""
    if mpid is None:
        return False
    return OptOutMpid.opting_out(config.admindb.session, mpid)


def gen_optout_rids() -> Generator[str, None, None]:
    # If a patient opts out, we need to be able to wipe their information from
    # the database, and hence look up their RID for that purpose.
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
# Functions for getting pids from restricted set
# =============================================================================

def get_valid_pid_subset(given_pids: List[any]) -> List[any]:
    """
    Takes a list of pids and returns those in the list which
    are also in the database.
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
            where(pidcol is not None).
            distinct()
        )
        result = session.execute(query)
        real_pids = [str(x[0]) for x in result]
        for pid in real_pids:
            if pid in given_pids:
                pids.append(pid)

    return pids


def get_subset_from_field(field: str, field_elements: List[any]) -> List[any]:
    """
    Takes a field name and elements from that field and queries the database
    to find the pids associated with these values.
    """
    pids = []
    # Get database, table and field from 'field'
    db_parts = field.split(".")
    # Database name
    db = db_parts[0]
    # Table name
    tablename = db_parts[1]
    # Field name
    fieldname = db_parts[2]
    pid_from_other_table = None
    try:
        session = config.sources[db].session
    except:
        print("Unable to connect to database {}. Remember argument to "
              "'--restrict' must be of the form 'database.table.field', "
              "or be 'pid'.".format(db))
    fieldcol = column(fieldname)
    for ddr in config.dd.rows:
        # Check if this is the pid column for the specified table
        if ddr.src_table == tablename and "P" in ddr.src_flags:
            pid_from_other_table = ddr.src_field
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
                where((fieldcol.in_(field_elements)) & (pidcol is not None)).
                distinct()
            )
            result = session.execute(query)
            pids.extend([x[0] for x in result])
            # As there is only one relavant database here, we return pids  
            return pids
        else:
            # Mark out row of dd with primary pid for relavant database
            row = ddr

    ####### Doesn't work! Trying in plain SQL #########
    ## Deal with case where the field specified isn't in the table
    ## with the primary pid
    #session = config.sources[db].session
    #pidcol = column(row.src_field)
    #session = config.sources[ddr.src_db].session
    #chosen_table = table(tablename)
    #ddr_table = table(row.src_table)
    #join_obj = ddr_table.join(chosen_table, chosen_table.c.fieldcol == ddr_table.c.pidcol)
    #query = (
    #    select([pidcol]).
    #    select_from(join_obj).
    #    where((chosen_table.fieldcol.in_(field_elements)) &
    #               (ddr_table.pidcol is not None)).
    #    distinct()
    #)

    ## Deal with case where the field specified isn't in the table
    ## with the primary pid
    session = config.sources[db].session
    source_field = row.src_field
    source_table = row.src_table
    # Convert list to string in correct form for query
    txt_elements = ", ".join(field_elements)
    txt_elements = "(" + txt_elements + ")"

    txt = "SELECT {}.{} FROM {} ".format(source_table,source_field,
               source_table)
    txt += "JOIN {} ON {}.{}={}.{} ".format(tablename, source_table,
               source_field, tablename, fieldname)
    txt += "WHERE {}.{} IN {}".format(tablename, fieldname, txt_elements)
    txt += "AND {}.{} IS NOT NULL".format(source_table, source_field)
    sql = text(txt)

    result = session.execute(sql)
    pids.extend([x[0] for x in result])

    return pids


def fieldname_is_pid(field: str) -> bool:
    """
    Checks if a field name is 'pid' or, if in the form 'database.table.field',
    is the name of a primary pid field.
    """ 
    field_is_pid = False
    if field == 'pid':
        field_is_pid = True
        return field_is_pid
    for ddr in config.dd.rows:
        if ddr.defines_primary_pids:
            if ddr.src_db + "." + ddr.src_field == field:
                field_is_pid = True
                return field_is_pid
    return field_is_pid


def get_pids_from_file(field: str, filename: str) -> List[int]:
    """"
    Takes a field name, and a filename of values of that field, and returns
    a list of pids associated with them.
    """
    field_is_pid = fieldname_is_pid(field)
    #pid_is_integer = config.pidtype_is_integer
    if field_is_pid:
        # If the chosen field is a pid field, just make sure all pids in the
        # file are valid
        given_pids = [x for x in gen_words_from_file(filename)]
        pids = get_valid_pid_subset(given_pids)
    else:
        field_elements = [x for x in gen_words_from_file(filename)]
        pids = get_subset_from_field(field, field_elements)

    return pids


def get_pids_from_list(field: str, list_elements: List[any]) -> List[int]:
    field_is_pid = fieldname_is_pid(field)
    if field_is_pid:
        pids = get_valid_pid_subset(list_elements)
    else:
        pids = get_subset_from_field(field, list_elements)

    return pids


def get_pids_from_limits(low: int, high: int) -> List[int]:
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


def get_pids_query_field_limits(field: str, low: int, high: int) -> List[int]:
    pids = []
    # Get database, table and field from 'field'
    db_parts = field.split(".")
    # Database name
    db = db_parts[0]
    # Table name
    tablename = db_parts[1]
    # Field name
    fieldname = db_parts[2]
    try:
        session = config.sources[db].session
    except:
        print("Unable to connect to database {}. Remember argument to "
              "'--restrict' must be of the form 'database.table.field', "
              "or be 'pid'.".format(db))
    fieldcol = column(fieldname)
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
        else:
            # Mark out row of dd with primary pid for relavant database
            row = ddr

    ## Deal with case where the field specified isn't in the table
    ## with the primary pid
    session = config.sources[db].session
    source_field = row.src_field
    source_table = row.src_table
    txt = "SELECT {}.{} FROM {} ".format(source_table,source_field,
               source_table)
    txt += "JOIN {} ON {}.{}={}.{} ".format(tablename, source_table,
               source_field, tablename, fieldname)
    txt += "WHERE ({}.{} BETWEEN {} AND {}) ".format(tablename, fieldname,
                                                  low, high)
    txt += "AND {}.{} IS NOT NULL".format(source_table, source_field)
    sql = text(txt)

    result = session.execute(sql)
    pids.extend([x[0] for x in result])

    return pids


def get_pids_from_field_limits(field: str, low: int, high: int) -> List[int]:
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
        specified_pids: List[int] = None) -> Generator[int, None, None]:
    """
    Generate patient IDs.

        sources: dictionary
            key: db name
            value: rnc_db database object
    """
    # ASSIGNS WORK TO THREADS/PROCESSES, via the simple expedient of processing
    # only those patient ID numbers where patientnum % ntasks == tasknum.

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
        log.debug("Looking for patient IDs in {}.{}".format(ddr.src_table,
                                                            ddr.src_field))
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
            log.debug("Found patient id: {}".format(patient_id))
            n_found += 1
            yield patient_id

            # Too many?
            if 0 < debuglimit <= n_found:
                log.warning(
                    "Not fetching more than {} patients (in total for this "
                    "process) due to debug_max_n_patients limit".format(
                        debuglimit))
                result.close()  # http://docs.sqlalchemy.org/en/latest/core/connections.html  # noqa
                return


def estimate_count_patients() -> int:
    """
    We can't easily and quickly get the total number of patients, because they
    may be defined in multiple tables across multiple databases. We shouldn't
    fetch them all into Python in case there are billions, and it's a waste of
    effort to stash them in a temporary table and count unique rows, because
    this is all only for a progress indicator. So we approximate:
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
    Generates rows from a source table
    ... each row being a list of values
    ... each value corresponding to a field in sourcefields.

    ... optionally restricted to a single patient

    If the table has a PK and we're operating in a multitasking situation,
    generate just the rows for this task (thread/process).
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
                    "Table {}.{}: not fetching more than {} rows (in total "
                    "for this process) due to debugging limits".format(
                        dbname, sourcetable, debuglimit))
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
    Generate (table, list-of-DD-rows-for-indexed-fields) tuples for all tables
    requiring indexing.
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
    Generate (source db name, source table) tuples for all tables that
    (a) don't contain patient information and
    (b) don't have an integer PK.
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
    Generate (source db name, source table, PK name) tuples for all tables that
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
                  ntasks: int = 1) -> None:
    """
    Process a table. This can either be a patient table (in which case the
    patient's scrubber is applied and only rows for that patient are processed)
    or not (in which case the table is just copied).
    """
    start = "process_table: {}.{}: ".format(sourcedbname, sourcetable)
    pid = None if patient is None else patient.get_pid()
    log.debug(start + "pid={}, incremental={}".format(pid, incremental))

    # Limit the data quantity for debugging?
    srccfg = config.sources[sourcedbname].srccfg
    if matches_tabledef(sourcetable, srccfg.debug_limited_tables):
        debuglimit = srccfg.debug_row_limit
        # log.debug("Limiting table {} to {} rows (per process)".format(
        #     sourcetable, debuglimit))
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
        # log.debug("DD row: {}".format(str(ddr)))
        if ddr.pk:
            pkfield_index = i
            src_pk_name = ddr.src_field
            dest_pk_name = ddr.dest_field
        sourcefields.append(ddr.src_field)
    srchash = None
    sqla_table = config.dd.get_dest_sqla_table(dest_table)
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
                start + "processing record {recnum}/{count}{for_pt} "
                "({progress})".format(
                    n=n, recnum=recnum+1, count=count,
                    for_pt=" for this patient" if pid is not None else "",
                    progress=config.overall_progress()))
        recnum += ntasks or 1
        if addhash:
            srchash = config.hash_object(row)
            if incremental and identical_record_exists_by_hash(
                    dest_table, dest_pk_name, row[pkfield_index], srchash):
                log.debug(
                    "... ... skipping unchanged record (identical by hash): "
                    "{sd}.{st}.{spkf} = "
                    "(destination) {dt}.{dpkf} = {pkv}".format(
                        sd=sourcedbname, st=sourcetable, spkf=src_pk_name,
                        dt=dest_table, dpkf=dest_pk_name,
                        pkv=row[pkfield_index]))
                continue
        if constant:
            if incremental and identical_record_exists_by_pk(
                    dest_table, dest_pk_name, row[pkfield_index]):
                log.debug(
                    "... ... skipping unchanged record (identical by PK and "
                    "marked as constant): {sd}.{st}.{spkf} = "
                    "(destination) {dt}.{dpkf} = {pkv}".format(
                        sd=sourcedbname, st=sourcetable, spkf=src_pk_name,
                        dt=dest_table, dpkf=dest_pk_name,
                        pkv=row[pkfield_index]))
                continue
        destvalues = {}
        skip_row = False
        for i, ddr in enumerate(ddrows):
            value = row[i]
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

    log.debug(start + "finished: pid={}".format(pid))
    commit_destdb()


def create_indexes(tasknum: int = 0, ntasks: int = 1) -> None:
    """
    Create indexes for the destination tables.
    """
    log.info(SEP + "Create indexes")
    engine = config.get_destdb_engine_outside_transaction()
    mssql = engine.dialect.name == 'mssql'
    mssql_fulltext_columns_by_table = []  # type: List[List[Column]]
    for (tablename, tablerows) in gen_index_row_sets_by_table(tasknum=tasknum,
                                                              ntasks=ntasks):
        sqla_table = config.dd.get_dest_sqla_table(tablename)
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
                          specified_pids: List[int] = None) -> None:
    """
    Iterate through patient IDs;
        build the scrubber for each patient;
        process source data for that patient, scrubbing it;
        insert the patient into the mapping table in the admin database.
    """
    n_patients = estimate_count_patients() // ntasks
    i = 0
    for pid in gen_patient_ids(tasknum, ntasks,
                               specified_pids=specified_pids):
        # gen_patient_ids() assigns the work to the appropriate thread/process
        # Check for an abort signal once per patient processed
        i += 1
        log.info(
            "Processing patient ID: {pid} (incremental={incremental}; "
            "patient {i}/~{n_patients} for this process; {progress})".format(
                pid=pid, incremental=incremental, i=i, n_patients=n_patients,
                progress=config.overall_progress()))

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
                "Skipping patient with PID={} as the following scrub_src "
                "fields are required and had no data: {}".format(
                    pid, patient.mandatory_scrubbers_unfulfilled))
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
            log.debug("Patient {}, processing database: {}".format(pid, d))
            for t in config.dd.get_patient_src_tables_with_active_dest(d):
                log.debug("Patient {}, processing table {}.{}".format(
                    pid, d, t))
                process_table(d, t,
                              patient=patient,
                              incremental=(incremental and patient_unchanged))

    commit_destdb()


def wipe_opt_out_patients(report_every: int = 1000,
                          chunksize: int = 10000) -> None:
    """
    Delete any data from patients that have opted out (after their data was
    processed on a previous occasion).
    (Slightly complicated by the fact that the destination database can't
    necessarily 'see' the mapping database, so we need to cache the RID keys in
    the destination database temporarily.)
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
        log.debug(start + "... inserting {} records".format(len(records_)))
        destsession.execute(temptable.insert(), records_)

    i = 0
    records = []  # type: List[Dict[str: Any]]
    for rid in gen_optout_rids():
        i += 1
        if report_every and i % report_every == 0:
            log.debug(start + "... src row# {}".format(i))
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
        log.debug(start + ": ... {}".format(dest_table_name))
        dest_table = config.dd.get_dest_sqla_table(dest_table_name)
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
    If incremental is True, doesn't drop tables; just deletes destination
    information where source information no longer exists.
    """
    log.info(SEP + "Creating database structure +/- deleting dead data")
    engine = config.admindb.engine
    if not incremental:
        log.info("Dropping admin tables except opt-out")
        # not OptOut
        PatientInfo.__table__.drop(engine, checkfirst=True)
        TridRecord.__table__.drop(engine, checkfirst=True)
    log.info("Creating admin tables")
    OptOutPid.__table__.create(engine, checkfirst=True)
    OptOutMpid.__table__.create(engine, checkfirst=True)
    PatientInfo.__table__.create(engine, checkfirst=True)
    TridRecord.__table__.create(engine, checkfirst=True)

    wipe_and_recreate_destination_db(incremental=incremental)
    if skipdelete or not incremental:
        return
    for d in config.dd.get_source_databases():
        for t in config.dd.get_src_tables(d):
            delete_dest_rows_with_no_src_row(
                d, t, report_every=config.report_every_n_rows,
                chunksize=config.chunksize)


def gen_integers_from_file(filename: str) -> Generator[int, None, None]:
    for line in open(filename):
        pids = [int(x) for x in line.split() if x.isdigit()]
        for pid in pids:
            yield pid


def gen_words_from_file(filename: str) -> Generator[str, None, None]:
    for line in open(filename):
        for pid in line.split():
            yield pid


def gen_opt_out_pids_from_file(mpid: bool = False) -> Generator[int,
                                                                None, None]:
    if mpid:
        text = "MPID"
        filenames = config.optout_mpid_filenames
        as_int = config.mpidtype_is_integer
    else:
        text = "PID"
        filenames = config.optout_pid_filenames
        as_int = config.pidtype_is_integer
    if not filenames:
        log.info("... no opt-out {} disk files in use".format(text))
    else:
        for filename in filenames:
            log.info("... {} file: {}".format(text, filename))
            if as_int:
                yield(gen_integers_from_file(filename))
            else:
                yield(gen_words_from_file(filename))


def gen_opt_out_pids_from_database(mpid: bool = False) -> Generator[int, None,
                                                                    None]:
    text = "MPID" if mpid else "PID"
    found_one = False
    defining_fields = config.dd.get_optout_defining_fields()
    for t in defining_fields:
        (src_db, src_table, optout_colname, pid_colname, mpid_colname) = t
        id_colname = mpid_colname if mpid else pid_colname
        if not id_colname:
            continue
        found_one = True
        session = config.sources[src_db].session
        log.info("... {}.{}.{} ({}={})".format(
            src_db, src_table, optout_colname, text, id_colname))
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
        log.info("... no opt-out-defining {} fields in data "
                 "dictionary".format(text))
        return


def setup_opt_out(incremental: bool = False) -> None:
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
    if not incremental:
        return
    wipe_opt_out_patients()


def process_nonpatient_tables(tasknum: int = 0,
                              ntasks: int = 1,
                              incremental: bool = False) -> None:
    """
    Copies all non-patient tables.
    If they have an integer PK, the work may be parallelized.
    If not, whole tables are assigned to different processes in parallel mode.
    """
    log.info(SEP + "Non-patient tables: (a) with integer PK")
    for (d, t, pkname) in gen_nonpatient_tables_with_int_pk():
        log.info("Processing non-patient table {}.{} (PK: {}) ({})...".format(
            d, t, pkname, config.overall_progress()))
        # noinspection PyTypeChecker
        process_table(d, t, patient=None,
                      incremental=incremental,
                      intpkname=pkname, tasknum=tasknum, ntasks=ntasks)
        commit_destdb()
    log.info(SEP + "Non-patient tables: (b) without integer PK")
    for (d, t) in gen_nonpatient_tables_without_int_pk(tasknum=tasknum,
                                                       ntasks=ntasks):
        log.info("Processing non-patient table {}.{} ({})...".format(
            d, t, config.overall_progress()))
        # Force this into single-task mode, i.e. we have already parallelized
        # by assigning different tables to different processes; don't split
        # the work within a single table.
        # noinspection PyTypeChecker
        process_table(d, t, patient=None,
                      incremental=incremental,
                      intpkname=None, tasknum=0, ntasks=1)
        commit_destdb()


def process_patient_tables(tasknum: int = 0,
                           ntasks: int = 1,
                           incremental: bool = False,
                           specified_pids: List[int] = None) -> None:
    """
    Process all patient tables, optionally in a parallel-processing fashion.
    """
    # We'll use multiple destination tables, so commit right at the end.
    log.info(SEP + "Patient tables")
    if ntasks == 1:
        log.info("Single-threaded, single-process mode")
    else:
        log.info("PROCESS {} (numbered from zero) OF {} PROCESSES".format(
            tasknum, ntasks))
    patient_processing_fn(tasknum=tasknum, ntasks=ntasks,
                          incremental=incremental,
                          specified_pids=specified_pids)

    if ntasks > 1:
        log.info("Process {}: FINISHED ANONYMISATION".format(tasknum))
    else:
        log.info("FINISHED ANONYMISATION")

    # Commit (should be redundant)
    commit_destdb()


def show_source_counts() -> None:
    """
    Show the number of records in all source tables.
    """
    print("SOURCE TABLE RECORD COUNTS:")
    counts = []  # type: List[Tuple[str, int]]
    for d in config.dd.get_source_databases():
        session = config.sources[d].session
        for t in config.dd.get_src_tables(d):
            n = count_star(session, t)
            counts.append(("{}.{}".format(d, t), n))
    print_record_counts(counts)


def show_dest_counts() -> None:
    """
    Show the number of records in all destination tables.
    """
    print("DESTINATION TABLE RECORD COUNTS:")
    counts = []  # type: List[Tuple[str, int]]
    session = config.destdb.session
    for t in config.dd.get_dest_tables():
        n = count_star(session, t)
        counts.append(("DESTINATION: {}".format(t), n))
    print_record_counts(counts)


# =============================================================================
# Main
# =============================================================================

def anonymise(args: Any) -> None:
    """
    Main entry point.
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
            print(args.list)
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
                               specified_pids=pids)

    # 4. Tables without any patient ID (e.g. lookup tables). Process PER TABLE.
    if args.nonpatienttables or everything:
        process_nonpatient_tables(tasknum=args.process,
                                  ntasks=args.nprocesses,
                                  incremental=args.incremental)

    # 5. Indexes. ALWAYS FASTEST TO DO THIS LAST. Process PER TABLE.
    if args.index or everything:
        create_indexes(tasknum=args.process, ntasks=args.nprocesses)

    log.info(BIGSEP + "Finished")
    end = get_now_utc_pendulum()
    time_taken = end - start
    log.info("Time taken: {} seconds".format(time_taken.total_seconds()))
    # config.dd.debug_cache_hits()
