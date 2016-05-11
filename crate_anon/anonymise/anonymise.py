#!/usr/bin/env python3
# crate_anon/anonymise/anonymise.py

"""
Anonymise multiple SQL-based databases using a data dictionary.

Author: Rudolf Cardinal
Created at: 18 Feb 2015
Last update: see VERSION_DATE below

Copyright/licensing:

    Copyright (C) 2015-2016 Rudolf Cardinal (rudolf@pobox.com).
    Department of Psychiatry, University of Cambridge.

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

"""

# =============================================================================
# Imports
# =============================================================================

import logging
import random
import sys

from sortedcontainers import SortedSet
from sqlalchemy.schema import (
    Column,
    Index,
    MetaData,
    Table,
)
from sqlalchemy.sql import (
    column,
    func,
    select,
    table,
)

from cardinal_pythonlib.rnc_datetime import (
    coerce_to_date,
    get_now_utc,
    truncate_date_to_first_of_month,
)
from cardinal_pythonlib.rnc_extract_text import document_to_text

from crate_anon.anonymise.config import config
from crate_anon.anonymise.constants import (
    ALTERMETHOD,
    INDEX,
    MYSQL_TABLE_ARGS,
    SEP,
)
from crate_anon.anonymise.models import OptOut, PatientInfo, TridRecord
from crate_anon.anonymise.patient import Patient
from crate_anon.anonymise.sqla import (
    count_star,
    get_column_names,
    add_index,
    plain_exists,
)

log = logging.getLogger(__name__)


# =============================================================================
# Database queries
# =============================================================================

def identical_record_exists_by_hash(dest_table, pkfield, pkvalue,
                                    hashvalue):
    """
    For a given PK in a given destination table, is there a record with the
    specified value for its source hash?
    """
    return plain_exists(config.destdb.session,
                        dest_table,
                        column(pkfield) == pkvalue,
                        column(config.source_hash_fieldname) == hashvalue)


def identical_record_exists_by_pk(dest_table, pkfield, pkvalue):
    """
    For a given PK in a given destination table, does a record exist?
    """
    return plain_exists(config.destdb.session,
                        dest_table,
                        column(pkfield) == pkvalue)


# =============================================================================
# Database actions
# =============================================================================

def wipe_and_recreate_destination_db(incremental=False):
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
        sqla_table.create(engine, checkfirst=True)
        # Check
        resulting_fieldnames = get_column_names(engine, tablename)
        target_set = set(sqla_table.columns.keys())
        outcome_set = set(resulting_fieldnames)
        missing = list(target_set - outcome_set)
        extra = list(outcome_set - target_set)
        if missing:
            raise Exception(
                "Missing fields in destination table {t}: {l}".format(
                    t=tablename, l=missing))
        if extra:
            log.warning(
                "Extra fields in destination table {t}: {l}".format(
                    t=tablename, l=extra))


def delete_dest_rows_with_no_src_row(srcdbname, src_table,
                                     report_every=1000, chunksize=10000):
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
        srcdbname, src_table, config.destdb.name, dest_table_name
    )
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
        Column(pkfield, pkddr.get_sqla_dest_coltype(), primary_key=True),
        **MYSQL_TABLE_ARGS
    )
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
    records = []
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
            records = []
    if records:  # remainder
        insert(records)
    commit_destdb()

    # 4. Index
    log.debug("... creating index on temporary table")
    index = Index('_temptable_idx', temptable.columns[pkfield])
    index.create(destengine)

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


def commit_destdb():
    """
    Execute a COMMIT on the destination database, and reset row counts.
    """
    config.destdb.session.commit()
    config.rows_in_transaction = 0
    config.bytes_in_transaction = 0


def commit_admindb():
    """
    Execute a COMMIT on the admin database, which is using ORM sessions.
    """
    config.admindb.session.commit()


# =============================================================================
# Opt-out
# =============================================================================

def opt_out(pid):
    """Does this patient wish to opt out?"""
    if pid is None:
        raise ValueError("opt_out(None) is nonsensical")
    return OptOut.opting_out(config.admindb.session, pid)


def gen_optout_rids():
    session = config.admindb.session
    return (
        session.query(PatientInfo.rid).
        filter(PatientInfo.pid.in_(session.query(OptOut.pid)))
    )  # ... is itself a generator


# =============================================================================
# Generators. Anything reading the main database should use a generator, so the
# script can scale to databases of arbitrary size.
# =============================================================================

def gen_patient_ids(tasknum=0, ntasks=1):
    """
    Generate patient IDs.

        sources: dictionary
            key: db name
            value: rnc_db database object
    """
    # ASSIGNS WORK TO THREADS/PROCESSES, via the simple expedient of processing
    # only those patient ID numbers where patientnum % ntasks == tasknum.

    if 1 < ntasks <= tasknum:
            raise Exception("Invalid tasknum {}; must be <{}".format(
                tasknum, ntasks))

    # If we're going to define based on >1 table, we need to keep track of
    # what we've processed. However, if we only have one table, we don't.
    # We can't use the mapping table easily (*), because it leads to thread/
    # process locking for database access. So we use a set.
    # (*) if not patient_id_exists_in_mapping_db(admindb, patient_id): ...

    # Debug option?
    if config.debug_pid_list:
        log.warning("USING MANUALLY SPECIFIED PATIENT ID LIST")
        for pid in config.debug_pid_list:
            if ntasks == 1 or pid % ntasks == tasknum:
                yield pid
        return

    # Otherwise do it properly:
    keeping_track = config.dd.n_definers > 1
    if keeping_track:
        processed_ids = set()
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
            distinct().
            order_by(pidcol)
        )
        if ntasks > 1:
            query = query.where(func.mod(pidcol, ntasks) == tasknum)
        result = session.execute(query)
        for row in result:
            # Extract ID
            patient_id = row[0]
            # Duplicate?
            if keeping_track:
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


def gen_rows(dbname, sourcetable, sourcefields, pid=None,
             pkname=None, tasknum=None, ntasks=None, debuglimit=0):
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

    # Restrict to one patient?
    if pid is not None:
        pidcol_name = config.dd.get_pid_name(dbname, sourcetable)
        q = q.where(column(pidcol_name) == pid)

    # Divide up rows across tasks?
    if pkname is not None and tasknum is not None and ntasks is not None:
        q = q.where(func.mod(column(pkname), ntasks) == tasknum)

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
        yield list(row)
        # yield dict(zip(row.keys(), row))
        # see also http://stackoverflow.com/questions/19406859
        config.rows_inserted_per_table[db_table_tuple] += 1


def gen_index_row_sets_by_table(tasknum=0, ntasks=1):
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


def gen_nonpatient_tables_without_int_pk(tasknum=0, ntasks=1):
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


def gen_nonpatient_tables_with_int_pk():
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


def gen_pks(srcdbname, tablename, pkname):
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

def process_table(sourcedbname, sourcetable,
                  patient=None, incremental=False,
                  pkname=None, tasknum=None, ntasks=None):
    """
    Process a table. This can either be a patient table (in which case the
    patient's scrubber is applied and only rows for that patient are process)
    or not (in which case the table is just copied).
    """
    start = "process_table: {}.{}: ".format(sourcedbname, sourcetable)
    pid = None if patient is None else patient.get_pid()
    log.debug(start + "pid={}, incremental={}".format(pid, incremental))

    # Limit the data quantity for debugging?
    srccfg = config.sources[sourcedbname].srccfg
    if sourcetable in srccfg.debug_limited_tables:
        debuglimit = srccfg.debug_row_limit
    else:
        debuglimit = 0

    ddrows = config.dd.get_rows_for_src_table(sourcedbname, sourcetable)
    addhash = any([ddr.add_src_hash for ddr in ddrows])
    addtrid = any([ddr.primary_pid for ddr in ddrows])
    constant = any([ddr.constant for ddr in ddrows])
    # If addhash or constant is true, there will also be at least one non-
    # omitted row, namely the source PK (by the data dictionary's validation
    # process).
    ddrows = [ddr
              for ddr in ddrows
              if (not ddr.omit) or (addhash and ddr.scrub_src)]
    if not ddrows:
        return
    dest_table = ddrows[0].dest_table
    sourcefields = []
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
    n = 0
    srchash = None
    sqla_table = config.dd.get_dest_sqla_table(dest_table)
    session = config.destdb.session

    for row in gen_rows(sourcedbname, sourcetable, sourcefields,
                        pid, debuglimit=debuglimit,
                        pkname=pkname, tasknum=tasknum, ntasks=ntasks):
        n += 1
        if n % config.report_every_n_rows == 0:
            log.info(start + "processing row {} of task set".format(n))
        if addhash:
            srchash = config.hash_object(row)
            if incremental and identical_record_exists_by_hash(
                    dest_table, dest_pk_name, row[pkfield_index], srchash):
                log.debug(
                    "... ... skipping unchanged record (identical by hash): "
                    "{sd}.{st}.{spkf} = "
                    "(destination) {dt}.{dpkf} = {pkv}".format(
                        sd=sourcedbname,
                        st=sourcetable,
                        spkf=src_pk_name,
                        dt=dest_table,
                        dpkf=dest_pk_name,
                        pkv=row[pkfield_index],
                    )
                )
                continue
        if constant:
            if incremental and identical_record_exists_by_pk(
                    dest_table, dest_pk_name, row[pkfield_index]):
                log.debug(
                    "... ... skipping unchanged record (identical by PK and "
                    "marked as constant): {sd}.{st}.{spkf} = "
                    "(destination) {dt}.{dpkf} = {pkv}".format(
                        sd=sourcedbname,
                        st=sourcetable,
                        spkf=src_pk_name,
                        dt=dest_table,
                        dpkf=dest_pk_name,
                        pkv=row[pkfield_index],
                    )
                )
                continue
        destvalues = {}
        for i, ddr in enumerate(ddrows):
            if ddr.omit:
                continue
            value = row[i]
            if ddr.primary_pid:
                assert(value == patient.get_pid())
                value = patient.get_rid()
            elif ddr.master_pid:
                value = config.encrypt_master_pid(value)
            elif ddr.truncate_date:
                try:
                    value = coerce_to_date(value)
                    value = truncate_date_to_first_of_month(value)
                except (ValueError, OverflowError):
                    log.warning(
                        "Invalid date received to {ALTERMETHOD.TRUNCATEDATE} "
                        "method: {v}".format(ALTERMETHOD=ALTERMETHOD, v=value))
                    value = None
            elif ddr.extract_text:
                value = extract_text(value, row, ddr, ddrows)

            if ddr.scrub:
                # Main point of anonymisation!
                value = patient.scrub(value)
            destvalues[ddr.dest_field] = value
        if addhash:
            destvalues[config.source_hash_fieldname] = srchash
        if addtrid:
            destvalues[config.trid_fieldname] = patient.get_trid()
        q = sqla_table.insert_on_duplicate().values(destvalues)
        session.execute(q)

        # Trigger an early commit?
        early_commit = False
        if config.max_rows_before_commit is not None:
            config.rows_in_transaction += 1
            if config.rows_in_transaction >= config.max_rows_before_commit:
                early_commit = True
        if config.max_bytes_before_commit is not None:
            config.bytes_in_transaction += sys.getsizeof(destvalues)
            # ... approximate!
            # Quicker than e.g. len(repr(...)), as judged by a timeit() call.
            if config.bytes_in_transaction >= config.max_bytes_before_commit:
                early_commit = True
        if early_commit:
            log.info(start + "Triggering early commit based on row/byte count")
            commit_destdb()

    log.debug(start + "finished: pid={}".format(pid))
    commit_destdb()


def extract_text(value, row, ddr, ddrows):
    """
    Take a field's value and return extracted text, for file-related fields,
    where the DD row indicates that this field contains a filename or a BLOB.
    """
    filename = None
    blob = None
    extension = None
    if ddr.extract_from_filename:
        filename = value
        log.debug("extract_text: disk file, filename={}".format(filename))
    else:
        blob = value
        extindex = next(
            (i for i, x in enumerate(ddrows)
                if x.src_field == ddr.extract_ext_field),
            None)
        if extindex is None:
            raise ValueError(
                "Bug: missing extension field for "
                "alter_method={}".format(ddr.alter_method))
        extension = row[extindex]
        log.debug("extract_text: database blob, extension={}".format(
            extension))
    try:
        value = document_to_text(filename=filename,
                                 blob=blob,
                                 extension=extension)
    except Exception as e:
        log.error(
            "Exception from document_to_text: {}".format(e))
        value = None
    return value


def create_indexes(tasknum=0, ntasks=1):
    """
    Create indexes for the destination tables.
    """
    log.info(SEP + "Create indexes")
    engine = config.destdb.engine
    for (tablename, tablerows) in gen_index_row_sets_by_table(tasknum=tasknum,
                                                              ntasks=ntasks):
        sqla_table = config.dd.get_dest_sqla_table(tablename)
        for tr in tablerows:
            sqla_column = sqla_table.columns[tr.dest_field]
            add_index(engine, sqla_column,
                      unique=(tr.index == INDEX.UNIQUE),
                      fulltext=(tr.index == INDEX.FULLTEXT),
                      length=tr.indexlen)
            # Extra index for TRID?
            if tr.primary_pid:
                add_index(engine, sqla_table.columns[config.trid_fieldname],
                          unique=(tr.index == INDEX.UNIQUE))


def patient_processing_fn(tasknum=0, ntasks=1, incremental=False):
    """
    Iterate through patient IDs;
        build the scrubber for each patient;
        process source data for that patient, scrubbing it;
        insert the patient into the mapping table in the admin database.
    """
    for pid in gen_patient_ids(tasknum, ntasks):
        # gen_patient_ids() assigns the work to the appropriate thread/process
        # Check for an abort signal once per patient processed
        log.info("Processing patient ID: {} (incremental={})".format(
            pid, incremental))

        # Opt out?
        if opt_out(pid):
            log.info("... opt out")
            continue

        # Gather scrubbing information for a patient. (Will save.)
        patient = Patient(pid)
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


def wipe_opt_out_patients(report_every=1000, chunksize=10000):
    """
    Delete any data from patients that have opted out.
    (Slightly complicated by the fact that the destination database can't
    necessarily 'see' the mapping database.)
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
        **MYSQL_TABLE_ARGS
    )
    log.debug(start + ": 1. dropping temporary table")
    temptable.drop(destengine, checkfirst=True)  # use engine, not session
    log.debug(start + ": 2. making temporary table")
    temptable.create(destengine, checkfirst=True)  # use engine, not session

    log.debug(start + ": 3. populating temporary table with RIDs")

    def insert(records_):
        log.debug(start + "... inserting {} records".format(len(records_)))
        destsession.execute(temptable.insert(), records_)

    i = 0
    records = []
    for rid in gen_optout_rids():
        i += 1
        if report_every and i % report_every == 0:
            log.debug(start + "... src row# {}".format(i))
        records.append([rid])
        if i % chunksize == 0:
            insert(records)
            records = []
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
    (
        adminsession.query(PatientInfo).
        filter(PatientInfo.pid.in_(adminsession.query(OptOut.pid))).
        delete(synchronize_session=False)
    )
    commit_admindb()


def drop_remake(incremental=False):
    """
    Drop and rebuild (a) mapping table, (b) destination tables.
    If incremental is True, doesn't drop tables; just deletes destination
    information where source information no longer exists.
    """
    engine = config.admindb.engine
    if not incremental:
        log.info("Dropping admin tables except opt-out")
        # not OptOut
        PatientInfo.__table__.drop(engine, checkfirst=True)
        TridRecord.__table__.drop(engine, checkfirst=True)
    log.info("Creating admin tables")
    OptOut.__table__.create(engine, checkfirst=True)
    PatientInfo.__table__.create(engine, checkfirst=True)
    TridRecord.__table__.create(engine, checkfirst=True)

    wipe_and_recreate_destination_db(incremental=incremental)
    if not incremental:
        return
    wipe_opt_out_patients()
    for d in config.dd.get_source_databases():
        for t in config.dd.get_src_tables(d):
            delete_dest_rows_with_no_src_row(
                d, t, report_every=config.report_every_n_rows)


def process_nonpatient_tables(tasknum=0, ntasks=1, incremental=False):
    """
    Copies all non-patient tables.
    If they have an integer PK, the work may be parallelized.
    """
    log.info(SEP + "Non-patient tables: (a) with integer PK")
    for (d, t, pkname) in gen_nonpatient_tables_with_int_pk():
        log.info("Processing non-patient table {}.{} (PK: {})...".format(
            d, t, pkname))
        process_table(d, t, patient=None,
                      incremental=incremental,
                      pkname=pkname, tasknum=tasknum, ntasks=ntasks)
        commit_destdb()
    log.info(SEP + "Non-patient tables: (b) without integer PK")
    for (d, t) in gen_nonpatient_tables_without_int_pk(tasknum=tasknum,
                                                       ntasks=ntasks):
        log.info("Processing non-patient table {}.{}...".format(d, t))
        process_table(d, t, patient=None,
                      incremental=incremental,
                      pkname=None, tasknum=None, ntasks=None)
        commit_destdb()


def process_patient_tables(process=0, nprocesses=1,  # nthreads=1,
                           incremental=False):
    """
    Process all patient tables, optionally in a parallel-processing fashion.
    """
    # We'll use multiple destination tables, so commit right at the end.
    log.info(SEP + "Patient tables")
    if nprocesses == 1:
        log.info("Single-threaded, single-process mode")
        patient_processing_fn(tasknum=0, ntasks=1, incremental=incremental)
    else:
        log.info("PROCESS {} (numbered from zero) OF {} PROCESSES".format(
            process, nprocesses))
        patient_processing_fn(tasknum=process, ntasks=nprocesses,
                              incremental=incremental)

    if nprocesses > 1:
        log.info("Process {}: FINISHED ANONYMISATION".format(process))
    else:
        log.info("FINISHED ANONYMISATION")

    # Commit (should be redundant)
    commit_destdb()


def show_source_counts():
    """
    Show the number of records in all source tables.
    """
    log.info("SOURCE TABLE RECORD COUNTS:")
    for d in config.dd.get_source_databases():
        session = config.sources[d].session
        for t in config.dd.get_src_tables(d):
            n = count_star(session, t)
            log.info("{}.{}: {} records".format(d, t, n))


def show_dest_counts():
    """
    Show the number of records in all destination tables.
    """
    log.info("DESTINATION TABLE RECORD COUNTS:")
    session = config.destdb.session
    for t in config.dd.get_dest_tables():
        n = count_star(session, t)
        log.info("DESTINATION: {}: {} records".format(t, n))


# =============================================================================
# Main
# =============================================================================

def anonymise(args):
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

    everything = not any([args.dropremake, args.nonpatienttables,
                          args.patienttables, args.index])

    # Load/validate config
    config.report_every_n_rows = args.report
    config.debug_scrubbers = args.debugscrubbers
    config.save_scrubbers = args.savescrubbers
    config.set_echo(args.echo)
    if not args.draftdd:
        config.load_dd()

    if args.draftdd or args.incrementaldd:
        # Note: the difference is that for incrementaldd, the data dictionary
        # will have been loaded from disk; for draftdd, it won't (so a
        # completely fresh one will be generated).
        config.dd.read_from_source_databases(
            default_omit=(not args.makeddpermitbydefaultdangerous))
        print(config.dd.get_tsv())
        return

    config.check_valid()

    if args.count:
        show_source_counts()
        show_dest_counts()
        return

    # random number seed
    random.seed(args.seed)

    # -------------------------------------------------------------------------

    log.info(SEP + "Starting")
    start = get_now_utc()

    # 1. Drop/remake tables. Single-tasking only.
    if args.dropremake or everything:
        drop_remake(incremental=args.incremental)

    # 2. Tables without any patient ID (e.g. lookup tables). Process PER TABLE.
    if args.nonpatienttables or everything:
        process_nonpatient_tables(tasknum=args.process,
                                  ntasks=args.nprocesses,
                                  incremental=args.incremental)

    # 3. Tables with patient info. (This bit supports multithreading.)
    #    Process PER PATIENT, across all tables, because we have to synthesize
    #    information to scrub across the entirety of that patient's record.
    if args.patienttables or everything:
        process_patient_tables(process=args.process,
                               # nthreads=args.threads,
                               nprocesses=args.nprocesses,
                               incremental=args.incremental)

    # 4. Indexes. ALWAYS FASTEST TO DO THIS LAST. Process PER TABLE.
    if args.index or everything:
        create_indexes(tasknum=args.process, ntasks=args.nprocesses)

    log.info(SEP + "Finished")
    end = get_now_utc()
    time_taken = end - start
    log.info("Time taken: {} seconds".format(time_taken.total_seconds()))
    # config.dd.debug_cache_hits()
