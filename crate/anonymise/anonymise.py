#!/usr/bin/env python3
# crate/anonymise/anonymise.py

"""
Anonymise multiple SQL-based databases using a data dictionary.

Author: Rudolf Cardinal
Created at: 18 Feb 2015
Last update: see VERSION_DATE below

Copyright/licensing:

    Copyright (C) 2015-2015 Rudolf Cardinal (rudolf@pobox.com).
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

import argparse
import logging
import multiprocessing
import operator
import random
import signal
import sys
import threading

from cardinal_pythonlib.rnc_datetime import (
    coerce_to_date,
    get_now_utc,
    truncate_date_to_first_of_month,
)
import cardinal_pythonlib.rnc_db as rnc_db
from cardinal_pythonlib.rnc_extract_text import document_to_text
import cardinal_pythonlib.rnc_log as rnc_log

from crate.anonymise.config import Config, DEMO_CONFIG
from crate.anonymise.constants import (
    ALTERMETHOD,
    BIGINT_UNSIGNED,
    INDEX,
    RAW_SCRUBBER_FIELDNAME_PATIENT,
    RAW_SCRUBBER_FIELDNAME_TP,
    SEP,
    SRCFLAG,
    TRID_CACHE_PID_FIELDNAME,
    TRID_CACHE_TRID_FIELDNAME,
    TRID_TYPE,
)
from crate.anonymise.patient import Patient
from crate.version import VERSION, VERSION_DATE

log = logging.getLogger(__name__)

# =============================================================================
# Predefined fieldspecs
# =============================================================================

AUDIT_FIELDSPECS = [
    dict(name="id", sqltype=BIGINT_UNSIGNED, pk=True, autoincrement=True,
         comment="Arbitrary primary key"),
    dict(name="when_access_utc", sqltype="DATETIME", notnull=True,
         comment="Date/time of access (UTC)", indexed=True),
    dict(name="source", sqltype="VARCHAR(20)", notnull=True,
         comment="Source (e.g. tablet, webviewer)"),
    dict(name="remote_addr",
         sqltype="VARCHAR(45)",  # http://stackoverflow.com/questions/166132
         comment="IP address of the remote computer"),
    dict(name="user", sqltype="VARCHAR(255)",
         comment="User name, where applicable"),
    dict(name="query", sqltype="TEXT",
         comment="SQL query (with arguments)"),
    dict(name="details", sqltype="TEXT",
         comment="Details of the access"),
]


# =============================================================================
# Database queries
# =============================================================================

def identical_record_exists_by_hash(destdb, dest_table, pkfield, pkvalue,
                                    hashvalue):
    """
    For a given PK in a given destination table, is there a record with the
    specified value for its source hash?
    """
    sql = """
        SELECT 1
        FROM {table}
        WHERE {pkfield}=?
        AND {srchashfield}=?
    """.format(
        table=dest_table,
        pkfield=pkfield,
        srchashfield=config.source_hash_fieldname,
    )
    args = [pkvalue, hashvalue]
    row = destdb.fetchone(sql, *args)
    return (row is not None and row[0] == 1)


def identical_record_exists_by_pk(destdb, dest_table, pkfield, pkvalue):
    """
    For a given PK in a given destination table, does a record exist?
    """
    sql = """
        SELECT 1
        FROM {table}
        WHERE {pkfield}=?
    """.format(
        table=dest_table,
        pkfield=pkfield,
    )
    args = [pkvalue]
    row = destdb.fetchone(sql, *args)
    return (row is not None and row[0] == 1)


# =============================================================================
# Database actions
# =============================================================================

def makeadmintable(admindb, tablename, fieldspecs):
    """Makes a table in the admin database. Uses the MySQL Barracuda
    settings if available."""
    admindb.create_or_update_table(tablename,
                                   fieldspecs,
                                   drop_superfluous_columns=True,
                                   dynamic=True,
                                   compressed=False)
    if not admindb.mysql_table_using_barracuda(tablename):
        admindb.mysql_convert_table_to_barracuda(tablename, compressed=False)


def recreate_audit_table(admindb):
    """Create/recreate the audit table (in the admin database)."""
    log.debug("recreate_audit_table")
    makeadmintable(admindb, config.audit_tablename, AUDIT_FIELDSPECS)


def recreate_opt_out_table(admindb):
    """Create/recreate the opt-out table (in the admin database)."""
    log.debug("recreate_opt_out_table")
    OPT_OUT_FIELDSPECS = [
        dict(name=config.mapping_patient_id_fieldname,
             sqltype=BIGINT_UNSIGNED, pk=True, comment="Patient ID"),
    ]
    makeadmintable(admindb, config.opt_out_tablename, OPT_OUT_FIELDSPECS)


def wipe_and_recreate_mapping_table(admindb, incremental=False):
    """
    Drop and rebuild the mapping table in the admin database.
    """
    log.debug("wipe_and_recreate_mapping_table")
    if not incremental:
        admindb.drop_table(config.secret_map_tablename)
    fieldspecs = [
        dict(name=config.mapping_patient_id_fieldname,
             sqltype=BIGINT_UNSIGNED, pk=True,
             comment="Patient ID (PID) (PK)"),
        dict(name=config.research_id_fieldname,
             sqltype=config.SQLTYPE_ENCRYPTED_PID, notnull=True,
             comment="Research ID (RID)"),
        dict(name=config.trid_fieldname, unique=True, notnull=True,
             sqltype=TRID_TYPE, autoincrement=True,
             comment="Transient integer research ID (TRID)"),
        dict(name=config.mapping_master_id_fieldname,
             sqltype=BIGINT_UNSIGNED,
             comment="Master patient ID (MPID)"),
        dict(name=config.master_research_id_fieldname,
             sqltype=config.SQLTYPE_ENCRYPTED_PID,
             comment="Master research ID (MRID)"),
        dict(name=config.source_hash_fieldname,
             sqltype=config.SQLTYPE_ENCRYPTED_PID,
             comment="Scrubber hash (for change detection)"),
        dict(name=RAW_SCRUBBER_FIELDNAME_PATIENT,
             sqltype="TEXT",
             comment="Raw patient scrubber (for debugging only)"),
        dict(name=RAW_SCRUBBER_FIELDNAME_TP,
             sqltype="TEXT",
             comment="Raw third-party scrubber (for debugging only)"),
    ]
    makeadmintable(admindb, config.secret_map_tablename, fieldspecs)


def wipe_and_recreate_trid_cache(admindb, incremental=False):
    """
    Drop and rebuild the TRID one-time pad cache in the admin database.
    """
    log.debug("wipe_and_recreate_trid_cache")
    if not incremental:
        admindb.drop_table(config.secret_trid_cache_tablename)
    fieldspecs = [
        dict(name=TRID_CACHE_PID_FIELDNAME,
             sqltype=BIGINT_UNSIGNED, pk=True,
             comment="Patient ID (PID) (PK)"),
        dict(name=TRID_CACHE_TRID_FIELDNAME, unique=True, notnull=True,
             sqltype=TRID_TYPE, autoincrement=True,
             comment="Transient integer research ID (TRID)"),
    ]
    makeadmintable(admindb, config.secret_trid_cache_tablename, fieldspecs)


def wipe_and_recreate_destination_db(destdb, dynamic=True, compressed=False,
                                     incremental=False):
    """
    Drop and recreate all destination tables (as specified in the DD) in the
    destination database.
    """
    log.debug("wipe_and_recreate_destination_db, incremental={}".format(
        incremental))
    if not destdb.is_mysql():
        dynamic = False
        compressed = False

    for t in config.dd.get_dest_tables():
        # Drop
        if not incremental:
            log.debug("dropping table {}".format(t))
            destdb.drop_table(t)

        # Recreate
        ddr = config.dd.get_rows_for_dest_table(t)
        ddr = sorted(ddr, key=operator.attrgetter("dest_field"))
        fieldspecs = []
        dest_fieldnames = []
        for r in ddr:
            if r.omit:
                continue
            fs = r.dest_field + " " + r.dest_datatype
            if SRCFLAG.PRIMARYPID in r.src_flags:
                fs += " NOT NULL"
            if SRCFLAG.PK in r.src_flags:
                fs += " PRIMARY KEY"
            dest_fieldnames.append(r.dest_field)
            if r.comment or config.append_source_info_to_comment:
                comment = r.comment or ""
                if config.append_source_info_to_comment:
                    comment += " [from {t}.{f}]".format(
                        t=r.src_table,
                        f=r.src_field,
                    )
                fs += " COMMENT " + rnc_db.sql_quote_string(comment)
            fieldspecs.append(fs)
            if SRCFLAG.ADDSRCHASH in r.src_flags:
                # append a special field
                fieldspecs.append(
                    config.source_hash_fieldname + " " +
                    config.SQLTYPE_ENCRYPTED_PID +
                    " COMMENT 'Hashed amalgamation of all source fields'")
                dest_fieldnames.append(config.source_hash_fieldname)
            if SRCFLAG.PRIMARYPID in r.src_flags:
                # append another special field
                fieldspecs.append(
                    config.trid_fieldname + " " +
                    BIGINT_UNSIGNED +
                    " NOT NULL" +
                    " COMMENT 'Transient integer research ID (TRID)'")
                dest_fieldnames.append(config.trid_fieldname)
        log.debug("creating table {}".format(t))
        sql = """
            CREATE TABLE IF NOT EXISTS {table} (
                {fieldspecs}
            )
            {dynamic}
            {compressed}
            CHARACTER SET utf8
            COLLATE utf8_general_ci
        """.format(
            table=t,
            fieldspecs=",".join(fieldspecs),
            dynamic="ROW_FORMAT=DYNAMIC" if dynamic else "",
            compressed="ROW_FORMAT=COMPRESSED" if compressed else "",
        )
        destdb.db_exec_literal(sql)
        resulting_fieldnames = destdb.fetch_column_names(t)
        target_set = set(dest_fieldnames)
        outcome_set = set(resulting_fieldnames)
        missing = list(target_set - outcome_set)
        extra = list(outcome_set - target_set)
        if missing:
            raise Exception(
                "Missing fields in destination table {t}: {l}".format(
                    t=t,
                    l=missing,
                )
            )
        if extra:
            log.warning(
                "Extra fields in destination table {t}: {l}".format(
                    t=t,
                    l=extra,
                )
            )


def delete_dest_rows_with_no_src_row(srcdb, srcdbname, src_table,
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
    dest_table = config.dd.get_dest_table_for_src_db_table(srcdbname,
                                                           src_table)
    pkddr = config.dd.get_pk_ddr(srcdbname, src_table)
    TEMPTABLE = config.temporary_tablename
    PKFIELD = "srcpk"
    START = "delete_dest_rows_with_no_src_row: {}.{} -> {}.{}: ".format(
        srcdbname, src_table, config.destination_database, dest_table
    )
    log.info(START + "[WARNING: MAY BE SLOW]")

    # 0. If there's no source PK, we just delete everythong
    if not pkddr:
        log.info("... No source PK; deleting everything")
        config.destdb.db_exec("DELETE FROM {}".format(dest_table))
        commit(config.destdb)
        return

    if SRCFLAG.ADDITION_ONLY in pkddr.src_flags:
        log.info("... Table marked as addition-only; not deleting anything")
        return

    # 1. Drop temporary table
    log.debug("... dropping temporary table")
    config.destdb.drop_table(TEMPTABLE)

    # 2. Make temporary table
    log.debug("... making temporary table")
    create_sql = """
        CREATE TABLE IF NOT EXISTS {table} (
            {pkfield} {sqltype} PRIMARY KEY
        )
    """.format(table=TEMPTABLE, pkfield=PKFIELD, sqltype=pkddr.dest_datatype)
    config.destdb.db_exec(create_sql)

    # 3. Populate temporary table, +/- PK translation
    def insert(records):
        log.debug(START + "... inserting {} records".format(len(records)))
        config.destdb.insert_multiple_records(TEMPTABLE, [PKFIELD], records)

    n = srcdb.count_where(src_table)
    log.debug("... populating temporary table")
    i = 0
    records = []
    for pk in gen_pks(srcdb, src_table, pkddr.src_field):
        i += 1
        if report_every and i % report_every == 0:
            log.debug(START + "... src row# {} / {}".format(i, n))
        if SRCFLAG.PRIMARYPID in pkddr.src_flags:
            pk = config.encrypt_primary_pid(pk)
        elif SRCFLAG.MASTERPID in pkddr.src_flags:
            pk = config.encrypt_master_pid(pk)
        records.append([pk])
        if i % chunksize == 0:
            insert(records)
            records = []
    if records:
        insert(records)
        records = []
    commit(config.destdb)

    # 4. Index
    log.debug("... creating index on temporary table")
    config.destdb.create_index(TEMPTABLE, PKFIELD)

    # 5. DELETE FROM ... WHERE NOT IN ...
    log.debug("... deleting from destination where appropriate")
    delete_sql = """
        DELETE FROM {dest_table}
        WHERE {dest_pk} NOT IN (
            SELECT {pkfield} FROM {temptable}
        )
    """.format(
        dest_table=pkddr.dest_table,
        dest_pk=pkddr.dest_field,
        pkfield=PKFIELD,
        temptable=TEMPTABLE,
    )
    config.destdb.db_exec(delete_sql)

    # 6. Drop temporary table
    log.debug("... dropping temporary table")
    config.destdb.drop_table(TEMPTABLE)

    # 7. Commit
    commit(config.destdb)


def commit(destdb):
    """
    Execute a COMMIT on the destination database, and reset row counts.
    """
    destdb.commit()
    config._rows_in_transaction = 0
    config._bytes_in_transaction = 0


# =============================================================================
# Audit
# =============================================================================

def audit(details,
          from_console=False, remote_addr=None, user=None, query=None):
    """
    Write an entry to the audit log (in the admin database).
    """
    if not remote_addr:
        remote_addr = config.session.ip_address if config.session else None
    if not user:
        user = config.session.user if config.session else None
    if from_console:
        source = "console"
    else:
        source = "webviewer"
    config.admindb.db_exec(
        """
            INSERT INTO {table}
                (when_access_utc, source, remote_addr, user, query, details)
            VALUES
                (?,?,?,?,?,?)
        """.format(table=config.audit_tablename),
        config.NOW_UTC_NO_TZ,  # when_access_utc
        source,
        remote_addr,
        user,
        query,
        details
    )


# =============================================================================
# Opt-out
# =============================================================================

def opt_out(pid):
    """Does this patient wish to opt out?"""
    if pid is None:
        raise ValueError("opt_out(None) is nonsensical")
    return config.admindb.count_where(
        config.opt_out_tablename,
        {config.mapping_patient_id_fieldname: pid}) > 0


# =============================================================================
# Generators. Anything reading the main database should use a generator, so the
# script can scale to databases of arbitrary size.
# =============================================================================

def gen_patient_ids(sources, tasknum=0, ntasks=1):
    """
    Generate patient IDs.

        sources: dictionary
            key: db name
            value: rnc_db database object
    """
    # ASSIGNS WORK TO THREADS/PROCESSES, via the simple expedient of processing
    # only those patient ID numbers where patientnum % ntasks == tasknum.

    if ntasks > 1 and tasknum >= ntasks:
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
        if SRCFLAG.DEFINESPRIMARYPIDS not in ddr.src_flags:
            continue
        threadcondition = ""
        if ntasks > 1:
            threadcondition = """
                AND {pidfield} % {ntasks} = {tasknum}
            """.format(
                pidfield=ddr.src_field,
                ntasks=ntasks,
                tasknum=tasknum,
            )
        sql = """
            SELECT DISTINCT {pidfield}
            FROM {table}
            WHERE {pidfield} IS NOT NULL
            {threadcondition}
            ORDER BY {pidfield}
        """.format(
            pidfield=ddr.src_field,
            table=ddr.src_table,
            threadcondition=threadcondition,
        )
        db = sources[ddr.src_db]
        cursor = db.cursor()
        db.db_exec_with_cursor(cursor, sql)
        row = cursor.fetchone()
        while row is not None:
            # Extract ID
            patient_id = row[0]
            # Duplicate?
            if keeping_track:
                if patient_id in processed_ids:
                    # we've done this one already; skip it this time
                    row = cursor.fetchone()
                    continue
                processed_ids.add(patient_id)
            # Valid one
            log.debug("Found patient id: {}".format(patient_id))
            n_found += 1
            yield patient_id
            # Too many?
            if debuglimit > 0 and n_found >= debuglimit:
                log.warning(
                    "Not fetching more than {} patients (in total for this "
                    "process) due to debug_max_n_patients limit".format(
                        debuglimit))
                return
            # Fetch the next
            row = cursor.fetchone()


def gen_rows(db, dbname, sourcetable, sourcefields, pid=None,
             pkname=None, tasknum=None, ntasks=None, debuglimit=0):
    """
    Generates rows from a source table
    ... each row being a list of values
    ... each value corresponding to a field in sourcefields.

    ... optionally restricted to a single patient

    If the table has a PK and we're operating in a multitasking situation,
    generate just the rows for this task (thread/process).
    """
    args = []
    whereconds = []

    # Restrict to one patient?
    if pid is not None:
        whereconds.append("{}=?".format(
            config.srccfg[dbname].ddgen_per_table_pid_field))
        args.append(pid)

    # Divide up rows across tasks?
    if pkname is not None and tasknum is not None and ntasks is not None:
        whereconds.append("{pk} % {ntasks} = {tasknum}".format(
            pk=pkname,
            ntasks=ntasks,
            tasknum=tasknum,
        ))

    where = ""
    if whereconds:
        where = " WHERE " + " AND ".join(whereconds)
    sql = """
        SELECT {fields}
        FROM {table}
        {where}
    """.format(
        fields=",".join(sourcefields),
        table=sourcetable,
        where=where,
    )
    cursor = db.cursor()
    db.db_exec_with_cursor(cursor, sql, *args)
    row = cursor.fetchone()
    db_table_tuple = (dbname, sourcetable)
    while row is not None:
        if (debuglimit > 0 and
                config._rows_inserted_per_table[db_table_tuple] >= debuglimit):
            if not config._warned_re_limits[db_table_tuple]:
                log.warning(
                    "Table {}.{}: not fetching more than {} rows (in total "
                    "for this process) due to debugging limits".format(
                        dbname, sourcetable, debuglimit))
                config._warned_re_limits[db_table_tuple] = True
            row = None  # terminate while loop
            continue
        yield list(row)  # convert from tuple to list so we can modify it
        row = cursor.fetchone()
        config._rows_inserted_per_table[db_table_tuple] += 1
    # log.debug("About to close cursor...")
    cursor.close()
    # log.debug("... cursor closed")
    db.java_garbage_collect()  # for testing


def gen_index_row_sets_by_table(tasknum=0, ntasks=1):
    """
    Generate (table, list-of-DD-rows-for-indexed-fields) tuples for all tables
    requiring indexing.
    """
    indexrows = [ddr for ddr in config.dd.rows
                 if ddr.index and not ddr.omit]
    tables = list(set([r.dest_table for r in indexrows]))
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
        table = pair[1]
        pkname = config.dd.get_int_pk_name(db, table)
        yield (db, table, pkname)


def gen_pks(db, table, pkname):
    """
    Generate PK values from a table.
    """
    sql = "SELECT {pk} FROM {table}".format(pk=pkname, table=table)
    return db.gen_fetchfirst(sql)


# =============================================================================
# Core functions
# =============================================================================
# - For multithreaded use, the patients are divvied up across the threads.
# - KEY THREADING RULE: ALL THREADS MUST HAVE FULLY INDEPENDENT DATABASE
#   CONNECTIONS.

def process_table(sourcedb, sourcedbname, sourcetable, destdb,
                  patient=None, incremental=False,
                  pkname=None, tasknum=None, ntasks=None):
    """
    Process a table. This can either be a patient table (in which case the
    patient's scrubber is applied and only rows for that patient are process)
    or not (in which case the table is just copied).
    """
    START = "process_table: {}.{}: ".format(sourcedbname, sourcetable)
    pid = None if patient is None else patient.get_pid()
    log.debug(START + "pid={}, incremental={}".format(pid, incremental))

    # Limit the data quantity for debugging?
    srccfg = config.srccfg[sourcedbname]
    if sourcetable in srccfg.debug_limited_tables:
        debuglimit = srccfg.debug_row_limit
    else:
        debuglimit = 0

    ddrows = config.dd.get_rows_for_src_table(sourcedbname, sourcetable)
    addhash = any([SRCFLAG.ADDSRCHASH in ddr.src_flags for ddr in ddrows])
    addtrid = any([SRCFLAG.PRIMARYPID in ddr.src_flags for ddr in ddrows])
    constant = any([SRCFLAG.CONSTANT in ddr.src_flags for ddr in ddrows])
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
    destfields = []
    pkfield_index = None
    for i, ddr in enumerate(ddrows):
        # log.debug("DD row: {}".format(str(ddr)))
        if SRCFLAG.PK in ddr.src_flags:
            pkfield_index = i
        sourcefields.append(ddr.src_field)
        if not ddr.omit:
            destfields.append(ddr.dest_field)
    if addhash:
        destfields.append(config.source_hash_fieldname)
    if addtrid:
        destfields.append(config.trid_fieldname)
    n = 0
    for row in gen_rows(sourcedb, sourcedbname, sourcetable, sourcefields,
                        pid, debuglimit=debuglimit,
                        pkname=pkname, tasknum=tasknum, ntasks=ntasks):
        n += 1
        if n % config.report_every_n_rows == 0:
            log.info(START + "processing row {} of task set".format(n))
        if addhash:
            srchash = config.hash_list(row)
            if incremental and identical_record_exists_by_hash(
                    destdb, dest_table, ddrows[pkfield_index].dest_field,
                    row[pkfield_index], srchash):
                log.debug(
                    "... ... skipping unchanged record (identical by hash): "
                    "{sd}.{st}.{spkf} = "
                    "(destination) {dt}.{dpkf} = {pkv}".format(
                        sd=sourcedbname,
                        st=sourcetable,
                        spkf=ddrows[pkfield_index].src_field,
                        dt=dest_table,
                        dpkf=ddrows[pkfield_index].dest_field,
                        pkv=row[pkfield_index],
                    )
                )
                continue
        if constant:
            if incremental and identical_record_exists_by_pk(
                    destdb, dest_table, ddrows[pkfield_index].dest_field,
                    row[pkfield_index]):
                log.debug(
                    "... ... skipping unchanged record (identical by PK and "
                    "marked as constant): {sd}.{st}.{spkf} = "
                    "(destination) {dt}.{dpkf} = {pkv}".format(
                        sd=sourcedbname,
                        st=sourcetable,
                        spkf=ddrows[pkfield_index].src_field,
                        dt=dest_table,
                        dpkf=ddrows[pkfield_index].dest_field,
                        pkv=row[pkfield_index],
                    )
                )
                continue
        destvalues = []
        for i, ddr in enumerate(ddrows):
            if ddr.omit:
                continue
            value = row[i]
            if SRCFLAG.PRIMARYPID in ddr.src_flags:
                assert(value == patient.get_pid())
                value = patient.get_rid()
            elif SRCFLAG.MASTERPID in ddr.src_flags:
                value = config.encrypt_master_pid(value)
            elif ddr._truncate_date:
                try:
                    value = coerce_to_date(value)
                    value = truncate_date_to_first_of_month(value)
                except:
                    log.warning(
                        "Invalid date received to {ALTERMETHOD.TRUNCATEDATE} "
                        "method: {v}".format(ALTERMETHOD=ALTERMETHOD, v=value))
                    value = None
            elif ddr._extract_text:
                value = extract_text(value, row, ddr, ddrows)

            if ddr._scrub:
                # Main point of anonymisation!
                value = patient.scrub(value)

            destvalues.append(value)
        if addhash:
            destvalues.append(srchash)
        if addtrid:
            destvalues.append(patient.get_trid())
        destdb.insert_record(dest_table, destfields, destvalues,
                             update_on_duplicate_key=True)

        # Trigger an early commit?
        early_commit = False
        if config.max_rows_before_commit is not None:
            config._rows_in_transaction += 1
            if config._rows_in_transaction >= config.max_rows_before_commit:
                early_commit = True
        if config.max_bytes_before_commit is not None:
            config._bytes_in_transaction += sys.getsizeof(destvalues)
            # ... approximate!
            # Quicker than e.g. len(repr(...)), as judged by a timeit() call.
            if config._bytes_in_transaction >= config.max_bytes_before_commit:
                early_commit = True
        if early_commit:
            log.info(START + "Triggering early commit based on row/byte count")
            commit(destdb)

    log.debug(START + "finished: pid={}".format(pid))
    commit(destdb)


def extract_text(value, row, ddr, ddrows):
    """
    Take a field's value and return extracted text, for file-related fields,
    where the DD row indicates that this field contains a filename or a BLOB.
    """
    filename = None
    blob = None
    extension = None
    if ddr._extract_from_filename:
        filename = value
    else:
        blob = value
        extindex = next(
            (i for i, x in enumerate(ddrows)
                if x.src_field == ddr._extract_ext_field),
            None)
        if extindex is None:
            raise ValueError(
                "Bug: missing extension field for "
                "alter_method={}".format(ddr.alter_method))
        extension = row[extindex]
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
    for (table, tablerows) in gen_index_row_sets_by_table(tasknum=tasknum,
                                                          ntasks=ntasks):
        # Process a table as a unit; this makes index creation faster.
        # http://dev.mysql.com/doc/innodb/1.1/en/innodb-create-index-examples.html  # noqa
        sqlbits_normal = []
        sqlbits_fulltext = []
        for tr in tablerows:
            column = tr.dest_field
            length = tr.indexlen
            is_unique = tr.index == INDEX.UNIQUE
            is_fulltext = tr.index == INDEX.FULLTEXT
            if is_fulltext:
                idxname = "_idxft_{}".format(column)
                sqlbit = "ADD FULLTEXT INDEX {name} ({column})".format(
                    name=idxname,
                    column=column,
                )
            else:
                idxname = "_idx_{}".format(column)
                sqlbit = "ADD {unique} INDEX {name} ({column}{length})".format(
                    name=idxname,
                    column=column,
                    length="" if length is None else "({})".format(length),
                    unique="UNIQUE" if is_unique else "",
                )
            if not config.destdb.index_exists(table, idxname):
                # because it will crash if you add it again!
                if is_fulltext:
                    sqlbits_fulltext.append(sqlbit)
                else:
                    sqlbits_normal.append(sqlbit)
            # Extra index for TRID?
            if SRCFLAG.PRIMARYPID in tr.src_flags:
                column = config.trid_fieldname
                idxname = "_idx_{}".format(column)
                if not config.destdb.index_exists(table, idxname):
                    sqlbits_normal.append(
                        "ADD {unique} INDEX {name} ({column})".format(
                            unique="UNIQUE" if is_unique else "",
                            name=idxname,
                            column=column,
                        )
                    )

        if sqlbits_normal:
            sql = "ALTER TABLE {table} {add_indexes}".format(
                table=table,
                add_indexes=", ".join(sqlbits_normal),
            )
            log.info(sql)
            config.destdb.db_exec(sql)
        for sqlbit in sqlbits_fulltext:  # must add one by one
            sql = "ALTER TABLE {table} {add_indexes}".format(
                table=table,
                add_indexes=sqlbit,
            )
            log.info(sql)
            config.destdb.db_exec(sql)
        # Index creation doesn't require a commit.


class PatientThread(threading.Thread):
    """
    Class for patient processing in a multithreaded environment.
    (DEPRECATED: use multiple processes instead.)
    """
    def __init__(self, sources, destdb, admindb, nthreads, threadnum,
                 abort_event, subthread_error_event,
                 incremental):
        """Initialize the thread."""
        threading.Thread.__init__(self)
        self.sources = sources
        self.destdb = destdb
        self.admindb = admindb
        self.nthreads = nthreads
        self.threadnum = threadnum
        self.abort_event = abort_event
        self.subthread_error_event = subthread_error_event
        self.exception = None
        self.incremental = incremental

    def run(self):
        """Run the thread."""
        try:
            patient_processing_fn(
                self.sources, self.destdb, self.admindb,
                tasknum=self.threadnum, ntasks=self.nthreads,
                abort_event=self.abort_event,
                incremental=self.incremental)
        except Exception as e:
            log.exception(
                "Setting subthread_error_event from thread {}".format(
                    self.threadnum))
            self.subthread_error_event.set()
            self.exception = e
            raise e  # to kill the thread

    def get_exception(self):
        """Return stored exception information."""
        return self.exception


def patient_processing_fn(sources, destdb, admindb,
                          tasknum=0, ntasks=1,
                          abort_event=None, multiprocess=False,
                          incremental=False):
    """
    Iterate through patient IDs;
        build the scrubber for each patient;
        process source data for that patient, scrubbing it;
        insert the patient into the mapping table in the admin database.
    """
    threadprefix = ""
    if ntasks > 1 and not multiprocess:
        threadprefix = "Thread {}: ".format(tasknum)
        log.info(
            threadprefix +
            "Started thread {} (of {} threads, numbered from 0)".format(
                tasknum, ntasks))

    for pid in gen_patient_ids(sources, tasknum, ntasks):
        # gen_patient_ids() assigns the work to the appropriate thread/process
        # Check for an abort signal once per patient processed
        if abort_event is not None and abort_event.is_set():
            log.error(threadprefix + "aborted")
            return
        log.info(
            threadprefix + "Processing patient ID: {} (incremental={})".format(
                pid, incremental))

        # Opt out?
        if opt_out(pid):
            log.info("... opt out")
            continue

        # Gather scrubbing information for a patient
        patient = Patient(sources, pid, admindb, config)

        patient_unchanged = patient.unchanged()
        if incremental:
            if patient_unchanged:
                log.debug("Scrubber unchanged; may save some time")
            else:
                log.debug("Scrubber new or changed; reprocessing in full")

        # Insert into mapping db
        patient.save_to_mapping_db()

        # For each source database/table...
        for d in config.dd.get_source_databases():
            log.debug("Processing database: {}".format(d))
            db = sources[d]
            for t in config.dd.get_patient_src_tables_with_active_dest(d):
                log.debug(
                    threadprefix + "Patient {}, processing table {}.{}".format(
                        pid, d, t))
                process_table(db, d, t, destdb, patient=patient,
                              incremental=(incremental and patient_unchanged))

    commit(destdb)


def wipe_opt_out_patients(report_every=1000, chunksize=10000):
    """
    Delete any data from patients that have opted out.
    (Slightly complicated by the fact that the destination database can't
    necessarily 'see' the mapping database.)
    """
    START = "wipe_opt_out_patients"
    log.info(START)
    TEMPTABLE = config.temporary_tablename
    PIDFIELD = config.mapping_patient_id_fieldname
    RIDFIELD = config.research_id_fieldname

    # 1. Drop temporary table
    log.debug("... dropping temporary table")
    config.destdb.drop_table(TEMPTABLE)

    # 2. Make temporary table
    log.debug("... making temporary table")
    create_sql = """
        CREATE TABLE IF NOT EXISTS {table} (
            {rid} {sqltype} PRIMARY KEY
        )
    """.format(table=TEMPTABLE, rid=RIDFIELD,
               sqltype=config.SQLTYPE_ENCRYPTED_PID)
    config.destdb.db_exec(create_sql)

    # 3. Populate temporary table with RIDs
    def insert(records):
        log.debug(START + "... inserting {} records".format(len(records)))
        config.destdb.insert_multiple_records(TEMPTABLE, [RIDFIELD], records)

    log.debug("... populating temporary table")
    i = 0
    records = []
    gensql = """
        SELECT {rid}
        FROM {mappingtable}
        INNER JOIN {optouttable}
        ON {mappingtable}.{pid} = {optouttable}.{pid}
    """.format(
        rid=RIDFIELD,
        mappingtable=config.secret_map_tablename,
        optouttable=config.opt_out_tablename,
        pid=PIDFIELD,
    )
    for rid in config.admindb.gen_fetchfirst(gensql):
        i += 1
        if report_every and i % report_every == 0:
            log.debug(START + "... src row# {}".format(i))
        records.append([rid])
        if i % chunksize == 0:
            insert(records)
            records = []
    if records:
        insert(records)
        records = []
    commit(config.destdb)

    # 4. For each patient destination table, DELETE FROM ... WHERE IN ...
    for dest_table in config.dd.get_dest_tables_with_patient_info():
        log.debug(START + "... deleting from {} where appropriate".format(
            dest_table))
        delete_sql = """
            DELETE FROM {dest_table}
            WHERE {rid} IN (
                SELECT {rid} FROM {temptable}
            )
        """.format(
            dest_table=dest_table,
            rid=RIDFIELD,
            temptable=TEMPTABLE,
        )
        config.destdb.db_exec(delete_sql)

    # 5. Drop temporary table
    log.debug("... dropping temporary table")
    config.destdb.drop_table(TEMPTABLE)

    # 6. Commit
    commit(config.destdb)

    # 7. Delete those entries from the mapping table
    config.admindb.db_exec("""
        DELETE FROM {mappingtable}
        WHERE {pid} IN (
            SELECT {pid}
            FROM {optouttable}
        )
    """.format(
        mappingtable=config.secret_map_tablename,
        optouttable=config.opt_out_tablename,
        pid=PIDFIELD,
    ))
    config.admindb.commit()


def drop_remake(incremental=False):
    """
    Drop and rebuild (a) mapping table, (b) destination tables.
    If incremental is True, doesn't drop tables; just deletes destination
    information where source information no longer exists.
    """
    recreate_audit_table(config.admindb)
    recreate_opt_out_table(config.admindb)
    wipe_and_recreate_mapping_table(config.admindb, incremental=incremental)
    wipe_and_recreate_trid_cache(config.admindb, incremental=incremental)
    wipe_and_recreate_destination_db(config.destdb, incremental=incremental)
    if not incremental:
        return
    wipe_opt_out_patients()
    for d in config.dd.get_source_databases():
        db = config.sources[d]
        for t in config.dd.get_src_tables(d):
            delete_dest_rows_with_no_src_row(
                db, d, t, report_every=config.report_every_n_rows)


def process_nonpatient_tables(tasknum=0, ntasks=1, incremental=False):
    """
    Copies all non-patient tables.
    If they have an integer PK, the work may be parallelized.
    """
    log.info(SEP + "Non-patient tables: (a) with integer PK")
    for (d, t, pkname) in gen_nonpatient_tables_with_int_pk():
        db = config.sources[d]
        log.info("Processing non-patient table {}.{} (PK: {})...".format(
            d, t, pkname))
        process_table(db, d, t, config.destdb, patient=None,
                      incremental=incremental,
                      pkname=pkname, tasknum=tasknum, ntasks=ntasks)
        commit(config.destdb)
    log.info(SEP + "Non-patient tables: (b) without integer PK")
    for (d, t) in gen_nonpatient_tables_without_int_pk(tasknum=tasknum,
                                                       ntasks=ntasks):
        db = config.sources[d]
        log.info("Processing non-patient table {}.{}...".format(d, t))
        process_table(db, d, t, config.destdb, patient=None,
                      incremental=incremental,
                      pkname=None, tasknum=None, ntasks=None)
        commit(config.destdb)


def process_patient_tables(nthreads=1, process=0, nprocesses=1,
                           incremental=False):
    """
    Process all patient tables, optionally in a parallel-processing fashion.
    """
    # We'll use multiple destination tables, so commit right at the end.

    def ctrl_c_handler(signum, frame):
        log.exception("CTRL-C")
        abort_threads()

    def abort_threads():
        abort_event.set()  # threads will notice and terminate themselves

    log.info(SEP + "Patient tables")
    if nthreads == 1 and nprocesses == 1:
        log.info("Single-threaded, single-process mode")
        patient_processing_fn(
            config.sources, config.destdb, config.admindb,
            tasknum=0, ntasks=1, multiprocess=False,
            incremental=incremental)
    elif nprocesses > 1:
        log.info("PROCESS {} (numbered from zero) OF {} PROCESSES".format(
            process, nprocesses))
        patient_processing_fn(
            config.sources, config.destdb, config.admindb,
            tasknum=process, ntasks=nprocesses, multiprocess=True,
            incremental=incremental)
    else:
        log.info(SEP + "ENTERING SINGLE-PROCESS, MULTITHREADING MODE")
        signal.signal(signal.SIGINT, ctrl_c_handler)
        threads = []
        mainthreadprefix = "Main thread: "
        # Start the threads. Each needs its own set of database connections.
        abort_event = threading.Event()
        abort_event.clear()
        subthread_error_event = threading.Event()
        subthread_error_event.clear()
        for threadnum in range(nthreads):
            destdb = config.get_database("destination_database")
            admindb = config.get_database("admin_database")
            sources = {}
            for srcname in config.src_db_names:
                sources[srcname] = config.get_database(srcname)
            thread = PatientThread(sources, destdb, admindb,
                                   nthreads, threadnum,
                                   abort_event, subthread_error_event,
                                   incremental)
            thread.start()
            threads.append(thread)
            log.info(mainthreadprefix + "Started thread {}".format(threadnum))
        # Run; wait for the threads to finish, or crash, or for a user abort
        try:
            running = True
            while running:
                # log.debug(mainthreadprefix + "ping")
                running = False
                if subthread_error_event.is_set():
                    log.exception(mainthreadprefix + "A thread has crashed")
                    for t in threads:
                        e = t.get_exception()
                        if e:
                            log.exception(
                                mainthreadprefix +
                                "Found crashed thread {}".format(
                                    t.threadnum))
                            raise e
                else:
                    for t in threads:
                        if t.is_alive():
                            running = True
                            t.join(1)  # timeout so it does NOT block
                        else:
                            log.debug(
                                mainthreadprefix +
                                "Found finished thread {}".format(
                                    t.threadnum))
                # time.sleep(1)
        except Exception as e:
            log.exception(mainthreadprefix +
                          "Exception detected in main thread")
            abort_threads()
            raise e  # will terminate main thread
        log.info(SEP + "LEAVING MULTITHREADING MODE")
        if abort_event.is_set():
            log.exception("Threads terminated abnormally")
            raise Exception("Threads terminated abnormally")
    if nprocesses > 1:
        log.info("Process {}: FINISHED ANONYMISATION".format(process))
    else:
        log.info("FINISHED ANONYMISATION")

    # Main-thread commit (should be redundant)
    commit(config.destdb)


def show_source_counts():
    """
    Show the number of records in all source tables.
    """
    log.info("SOURCE TABLE RECORD COUNTS:")
    for d in config.dd.get_source_databases():
        db = config.sources[d]
        for t in config.dd.get_src_tables(d):
            n = db.count_where(t)
            log.info("{}.{}: {} records".format(d, t, n))


def show_dest_counts():
    """
    Show the number of records in all destination tables.
    """
    log.info("DESTINATION TABLE RECORD COUNTS:")
    db = config.destdb
    for t in config.dd.get_dest_tables():
        n = db.count_where(t)
        log.info("DESTINATION: {}: {} records".format(t, n))


# =============================================================================
# Main
# =============================================================================

def fail():
    """
    Exit with a failure code.
    """
    sys.exit(1)


def main():
    """
    Command-line entry point.
    """
    version = "Version {} ({})".format(VERSION, VERSION_DATE)
    description = """
Database anonymiser. {version}. By Rudolf Cardinal.

Sample usage (having set PYTHONPATH):
    anonymise.py -c > testconfig.ini  # generate sample config file
    anonymise.py -d testconfig.ini > testdd.tsv  # generate draft data dict.
    anonymise.py testconfig.ini  # run""".format(version=version)
    ncpus = multiprocessing.cpu_count()

    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-n", "--version", action="version", version=version)
    parser.add_argument('--verbose', '-v', action='count', default=0,
                        help="Be verbose (use twice for extra verbosity)")
    parser.add_argument('-r', '--report', nargs="?", type=int, default=1000,
                        help="Report insert progress every n rows in verbose "
                             "mode (default 1000)")
    parser.add_argument('-t', '--threads', nargs="?", type=int, default=1,
                        help="For multithreaded mode: number of threads to "
                             "use (default 1; this machine has {} "
                             "CPUs)".format(ncpus))
    parser.add_argument("configfile", nargs="?",
                        help="Configuration file name")
    parser.add_argument("--process", nargs="?", type=int, default=0,
                        help="For multiprocess patient-table mode: specify "
                             "process number")
    parser.add_argument("--nprocesses", nargs="?", type=int, default=1,
                        help="For multiprocess patient-table mode: specify "
                             "total number of processes (launched somehow, of "
                             "which this is to be one)")
    parser.add_argument("--processcluster", default="",
                        help="Process cluster name")
    parser.add_argument("--democonfig", action="store_true",
                        help="Print a demo config file (INCLUDES MORE HELP)")
    parser.add_argument("--draftdd", action="store_true",
                        help="Print a draft data dictionary")
    parser.add_argument("--incrementaldd", action="store_true",
                        help="Print an INCREMENTAL draft data dictionary")
    parser.add_argument("--makeddpermitbydefaultdangerous",
                        action="store_true",
                        help="When creating or adding to a data dictionary, "
                             "set the 'omit' flag to False. DANGEROUS.")
    parser.add_argument("--debugscrubbers", action="store_true",
                        help="Report sensitive scrubbing information, for "
                             "debugging")
    parser.add_argument("--savescrubbers", action="store_true",
                        help="Saves sensitive scrubbing information in admin "
                             "database, for debugging")
    parser.add_argument("--count", action="store_true",
                        help="Count records in source/destination databases, "
                             "then stop")
    parser.add_argument("--dropremake", action="store_true",
                        help="Drop/remake destination tables, then stop")
    parser.add_argument("--nonpatienttables", action="store_true",
                        help="Process non-patient tables only")
    parser.add_argument("--patienttables", action="store_true",
                        help="Process patient tables only")
    parser.add_argument("--index", action="store_true",
                        help="Create indexes only")
    parser.add_argument("-i", "--incremental", action="store_true",
                        help="Process only new/changed information, where "
                             "possible")
    parser.add_argument("--seed",
                        help="String to use as the basis of the seed for the "
                             "random number generator used for the transient "
                             "integer RID (TRID). Leave blank to use the "
                             "default seed (system time).")
    args = parser.parse_args()
    # log.error(args)

    # Demo config?
    if args.democonfig:
        print(DEMO_CONFIG)
        return

    # Validate args
    if not args.configfile:
        parser.print_help()
        fail()
    if args.nprocesses < 1:
        log.error("--nprocesses must be >=1")
        fail()
    if args.process < 0 or args.process >= args.nprocesses:
        log.error(
            "--process argument must be from 0 to (nprocesses - 1) inclusive")
        fail()
    if args.nprocesses > 1 and args.threads > 1:
        log.error("Can't use multithreading and multi-process mode. "
                  "In multi-process mode, specify --threads=1")
        fail()
    # Inefficient code but helpful error messages:
    if args.threads > 1 and args.dropremake:
        log.error("Can't use nthreads > 1 with --dropremake")
        fail()
    if args.threads > 1 and args.nonpatienttables:
        log.error("Can't use nthreads > 1 with --nonpatienttables")
        fail()
    if args.threads > 1 and args.index:
        log.error("Can't use nthreads > 1 with --index")
        fail()
    if args.nprocesses > 1 and args.dropremake:
        log.error("Can't use nprocesses > 1 with --dropremake")
        fail()
    if args.incrementaldd and args.draftdd:
        log.error("Can't use --incrementaldd and --draftdd")
        fail()

    everything = not any([args.dropremake, args.nonpatienttables,
                          args.patienttables, args.index])

    # -------------------------------------------------------------------------

    # Verbosity
    mynames = []
    if args.processcluster:
        mynames.append(args.processcluster)
    if args.nprocesses > 1:
        mynames.append("process {}".format(args.process))
    LOG_FORMAT = '%(asctime)s.%(msecs)03d:%(levelname)s:%(name)s:%(message)s'
    LOG_DATEFMT = '%Y-%m-%d %H:%M:%S'
    mainloglevel = logging.DEBUG if args.verbose >= 1 else logging.INFO
    logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATEFMT,
                        level=mainloglevel)
    rootlog = logging.getLogger()
    rnc_log.reset_logformat_timestamped(
        rootlog,
        extraname=" ".join(mynames),
        level=mainloglevel
    )
    rnc_db.set_loglevel(logging.DEBUG if args.verbose >= 2 else logging.INFO)

    # Load/validate config
    config.set(filename=args.configfile, load_dd=(not args.draftdd),
               load_destfields=False)
    config.report_every_n_rows = args.report
    config.debug_scrubbers = args.debugscrubbers
    config.save_scrubbers = args.savescrubbers

    if args.draftdd or args.incrementaldd:
        # Note: the difference is that for incrementaldd, the data dictionary
        # will have been loaded from disk; for draftdd, it won't (so a
        # completely fresh one will be generated).
        config.dd.read_from_source_databases(
            default_omit=(not args.makeddpermitbydefaultdangerous))
        print(config.dd.get_tsv())
        return

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
        process_patient_tables(nthreads=args.threads,
                               process=args.process,
                               nprocesses=args.nprocesses,
                               incremental=args.incremental)

    # 4. Indexes. ALWAYS FASTEST TO DO THIS LAST. Process PER TABLE.
    if args.index or everything:
        create_indexes(tasknum=args.process, ntasks=args.nprocesses)

    log.info(SEP + "Finished")
    end = get_now_utc()
    time_taken = end - start
    log.info("Time taken: {} seconds".format(time_taken.total_seconds()))


# =============================================================================
# Config instance, as process-local storage
# =============================================================================

config = Config()


# =============================================================================
# Command-line entry point
# =============================================================================

if __name__ == '__main__':
    main()
