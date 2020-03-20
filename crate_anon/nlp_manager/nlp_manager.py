#!/usr/bin/env python

"""
crate_anon/nlp_manager/nlp_manager.py

===============================================================================

    Copyright (C) 2015-2020 Rudolf Cardinal (rudolf@pobox.com).

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

**Manage natural-language processing (NLP) via internal and external tools.**

Speed testing:

- 8 processes, extracting person, location from a mostly text database
- commit off during full (non-incremental) processing (much faster)
- needs lots of RAM; e.g. Java subprocess uses 1.4 Gb per process as an
  average (rises from ~250Mb to ~1.4Gb and falls; steady rise means memory
  leak!); tested on a 16 Gb machine. See also the ``max_external_prog_uses``
  parameter.

.. code-block:: python

    from __future__ import division
    test_size_mb = 1887
    n_person_tags_found =
    n_locations_tags_found =
    time_s = 10333  # 10333 s for main bit; 10465 including indexing; is 2.9 hours
    speed_mb_per_s = test_size_mb / time_s

... gives 0.18 Mb/s, and note that's 1.9 Gb of *text*, not of attachments.

- With incremental option, and nothing to do: same run took 18 s.
- During the main run, snapshot CPU usage:

  .. code-block:: none

        java about 81% across all processes, everything else close to 0
            (using about 12 Gb RAM total)
        ... or 75-85% * 8 [from top]
        mysqld about 18% [from top]
        nlp_manager.py about 4-5% * 8 [from top]

"""  # noqa

# =============================================================================
# Imports
# =============================================================================

import argparse
import csv
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Tuple, Generator, TYPE_CHECKING

from cardinal_pythonlib.datetimefunc import get_now_utc_pendulum
from cardinal_pythonlib.exceptions import die
from cardinal_pythonlib.fileops import purge
from cardinal_pythonlib.logs import configure_logger_for_colour
from cardinal_pythonlib.sqlalchemy.core_query import count_star
from cardinal_pythonlib.timing import MultiTimerContext, timer
from sqlalchemy.engine.base import Engine
from sqlalchemy.orm.session import Session
from sqlalchemy.schema import Column, Index, MetaData, Table
from sqlalchemy.types import BigInteger, String

from crate_anon.anonymise.constants import (
    DEFAULT_CHUNKSIZE,
    DEFAULT_REPORT_EVERY,
    TABLE_KWARGS,
    SEP,
)
from crate_anon.anonymise.dbholder import DatabaseHolder
from crate_anon.common.formatting import print_record_counts
from crate_anon.nlp_manager.all_processors import (
    make_nlp_parser_unconfigured,
    possible_processor_names,
    possible_processor_table,
)
from crate_anon.nlp_manager.base_nlp_parser import TextProcessingFailed
from crate_anon.nlp_manager.constants import (
    DEFAULT_REPORT_EVERY_NLP,
    MAX_STRING_PK_LENGTH,
    NLP_CONFIG_ENV_VAR,
)
from crate_anon.nlp_manager.input_field_config import (
    InputFieldConfig,
    FN_SRCDB,
    FN_SRCTABLE,
    FN_SRCPKFIELD,
    FN_SRCPKVAL,
    FN_SRCPKSTR,
    FN_SRCFIELD,
    TRUNCATED_FLAG,
)
from crate_anon.nlp_manager.models import FN_SRCHASH, NlpRecord
from crate_anon.nlp_manager.nlp_definition import (
    NlpDefinition,
    demo_nlp_config,
)
from crate_anon.nlp_manager.cloud_parser import Cloud
from crate_anon.nlp_manager.cloud_request import (
    CloudRequest,
    CloudRequestListProcessors,
    CloudRequestProcess,
    CloudRequestQueueManagement,
)
from crate_anon.nlp_manager.cloud_run_info import CloudRunInfo
from crate_anon.nlprp.constants import NlprpKeys as NKeys
from crate_anon.version import CRATE_VERSION, CRATE_VERSION_DATE
# from crate_anon.common.profiling import do_cprofile

if TYPE_CHECKING:
    from http.cookiejar import CookieJar

log = logging.getLogger(__name__)

TIMING_DROP_REMAKE = "drop_remake"
TIMING_DELETE_WHERE_NO_SOURCE = "delete_where_no_source"
TIMING_PROGRESS_DB_ADD = "progress_db_add"


# =============================================================================
# Simple information classes
# =============================================================================

class DbInfo(object):
    """
    Simple object carrying information about a database.
    Used by :func:`delete_where_no_source`.
    """
    def __init__(self,
                 session: Session = None,
                 engine: Engine = None,
                 metadata: MetaData = None,
                 db: DatabaseHolder = None,
                 temptable: Table = None) -> None:
        self.session = session
        self.engine = engine
        self.metadata = metadata
        self.db = db
        self.temptable = temptable


# =============================================================================
# Database operations
# =============================================================================

def delete_where_no_source(nlpdef: NlpDefinition,
                           ifconfig: InputFieldConfig,
                           report_every: int = DEFAULT_REPORT_EVERY,
                           chunksize: int = DEFAULT_CHUNKSIZE) -> None:
    """
    Delete destination records where source records no longer exist.

    Args:
        nlpdef:
            :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
        ifconfig:
            `crate_anon.nlp_manager.input_field_config.InputFieldConfig`
        report_every:
            report to the log every *n* source rows
        chunksize:
            insert into the SQLAlchemy session every *n* records

    Development thoughts:

    - Can't do this in a single SQL command, since the engine can't necessarily
      see both databases.
    - Can't use a single temporary table, since the progress database isn't
      necessarily the same as any of the destination database(s).
    - Can't do this in a multiprocess way, because we're trying to do a
      ``DELETE WHERE NOT IN``.
    - So my first attempt was: fetch all source PKs (which, by definition, do
      exist), stash them in memory, and do a ``DELETE WHERE NOT IN`` based on
      those specified values (or, if there are no PKs in the source, delete
      everything from the destination).

    Problems with that:

    - This is IMPERFECT if we have string source PKs and there are hash
      collisions (e.g. PKs for records X and Y both hash to the same thing;
      record X is deleted; then its processed version might not be).
    - With massive tables, we might run out of memory or (much more likely)
      SQL parameter slots. -- This is now happening; error looks like:
      pyodbc.ProgrammingError: ('The SQL contains 30807 parameter parkers, but
      2717783 parameters were supplied', 'HY000')

    A better way might be:

    - for each table, make a temporary table in the same database
    - populate that table with (source PK integer/hash, source PK string) pairs
    - delete where pairs don't match -- is that portable SQL?
      http://stackoverflow.com/questions/7356108/sql-query-for-deleting-rows-with-not-in-using-2-columns  # noqa

    More efficient would be to make one table per destination database.

    On the "delete where multiple fields don't match":

    - Single field syntax is

      .. code-block:: sql

        DELETE FROM a WHERE a1 NOT IN (SELECT b1 FROM b)

    - Multiple field syntax is

      .. code-block:: sql

        DELETE FROM a WHERE NOT EXISTS (
            SELECT 1 FROM b
            WHERE a.a1 = b.b1
            AND a.a2 = b.b2
        )

    - In SQLAlchemy, :func:`exists`:

      - http://stackoverflow.com/questions/14600619
      - http://docs.sqlalchemy.org/en/latest/core/selectable.html

    - Furthermore, in SQL ``NULL = NULL`` is false (it's null), and ``NULL <>
      NULL`` is also false (it's null), so we have to do an explicit null
      check. You do that with ``field == None``. See
      http://stackoverflow.com/questions/21668606. We're aiming, therefore,
      for:

      .. code-block:: sql

        DELETE FROM a WHERE NOT EXISTS (
            SELECT 1 FROM b
            WHERE a.a1 = b.b1
            AND (
                a.a2 = b.b2
                OR (a.a2 IS NULL AND b.b2 IS NULL)
            )
        )

    """

    # -------------------------------------------------------------------------
    # Sub-functions
    # -------------------------------------------------------------------------

    def insert(records_: List[Dict[str, Any]]) -> None:
        n_rows = len(records_)
        log.debug(f"... inserting {n_rows} records")
        for db in databases:
            db.session.execute(db.temptable.insert(), records_)
            nlpdef.notify_transaction(db.session, n_rows=n_rows,
                                      n_bytes=sys.getsizeof(records_))

    def commit() -> None:
        for db in databases:
            nlpdef.commit(db.session)

    # -------------------------------------------------------------------------
    # Main code
    # -------------------------------------------------------------------------
    # Use info log level, otherwise it looks like our code hangs with very
    # large databases.

    log.info(f"delete_where_no_source: examining source table "
             f"{ifconfig.get_srcdb()}.{ifconfig.get_srctable()}; MAY BE SLOW")

    # Start our list with the progress database
    databases = [DbInfo(
        session=nlpdef.get_progdb_session(),
        engine=nlpdef.get_progdb_engine(),
        metadata=nlpdef.get_progdb_metadata(),
        db=nlpdef.get_progdb(),
        temptable=None
    )]

    # Add the processors' destination databases
    for processor in nlpdef.get_processors():  # of type TableMaker
        if isinstance(processor, Cloud) and not processor.available_remotely:
            continue
        session = processor.get_session()
        if any(x.session == session for x in databases):
            continue  # already exists
        databases.append(DbInfo(
            session=session,
            engine=processor.get_engine(),
            metadata=processor.get_metadata(),
            db=processor.get_destdb(),
        ))

    # Make a temporary table in each database (note: the Table objects become
    # affiliated to their engine, I think, so make separate ones for each).
    log.info(f"... using {len(databases)} destination database(s)")
    log.info("... dropping (if exists) and creating temporary table(s)")
    for database in databases:
        temptable = Table(
            nlpdef.get_temporary_tablename(),
            database.metadata,
            Column(FN_SRCPKVAL, BigInteger),  # not PK, as may be a hash
            Column(FN_SRCPKSTR, String(MAX_STRING_PK_LENGTH)),
            **TABLE_KWARGS
        )
        temptable.drop(database.engine, checkfirst=True)
        temptable.create(database.engine, checkfirst=True)
        database.temptable = temptable

    # Insert PKs into temporary tables

    n = count_star(ifconfig.get_source_session(), ifconfig.get_srctable())
    log.info(f"... populating temporary table(s): {n} records to go; "
             f"working in chunks of {chunksize}")
    i = 0
    records = []  # type: List[Dict[str, Any]]
    for pkval, pkstr in ifconfig.gen_src_pks():
        i += 1
        if report_every and i % report_every == 0:
            log.info(f"... src row# {i} / {n}")
        records.append({FN_SRCPKVAL: pkval, FN_SRCPKSTR: pkstr})
        if i % chunksize == 0:
            insert(records)
            records = []  # type: List[Dict[str, Any]]
    if records:  # remainder
        insert(records)

    # Commit
    commit()

    # Index, for speed
    log.info("... creating index(es) on temporary table(s)")
    for database in databases:
        temptable = database.temptable
        index = Index('_temptable_idx', temptable.columns[FN_SRCPKVAL])
        index.create(database.engine)

    # DELETE FROM desttable WHERE destpk NOT IN (SELECT srcpk FROM temptable)
    log.info("... deleting from progress/destination DBs where appropriate")

    # Delete from progress database
    prog_db = databases[0]
    prog_temptable = prog_db.temptable
    ifconfig.delete_progress_records_where_srcpk_not(prog_temptable)

    # Delete from others
    for processor in nlpdef.get_processors():
        if isinstance(processor, Cloud) and not processor.available_remotely:
            continue
        database = [x for x in databases
                    if x.session == processor.get_session()][0]
        temptable = database.temptable
        processor.delete_where_srcpk_not(ifconfig, temptable)

    # Drop temporary tables
    log.info("... dropping temporary table(s)")
    for database in databases:
        database.temptable.drop(database.engine, checkfirst=True)

    # Commit
    commit()

    # Update metadata to reflect the fact that the temporary tables have been
    # dropped
    for database in databases:
        database.db.update_metadata()


def drop_remake(nlpdef: NlpDefinition,
                incremental: bool = False,
                skipdelete: bool = False,
                report_every: int = DEFAULT_REPORT_EVERY,
                chunksize: int = DEFAULT_CHUNKSIZE) -> None:
    """
    Drop output tables and recreate them.

    Args:
        nlpdef:
            :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
        incremental: incremental processing mode?
        skipdelete:
            For incremental updates, skip deletion of rows present in the
            destination but not the source
        report_every: report to the log every *n* source rows
        chunksize: insert into the SQLAlchemy session every *n* records
    """
    # Not parallel.
    # -------------------------------------------------------------------------
    # 1. Progress database
    # -------------------------------------------------------------------------
    progengine = nlpdef.get_progdb_engine()
    if not incremental:
        log.debug("Dropping progress tables")
        # noinspection PyUnresolvedReferences
        NlpRecord.__table__.drop(progengine, checkfirst=True)
    log.info("Creating progress table (with index)")
    # noinspection PyUnresolvedReferences
    NlpRecord.__table__.create(progengine, checkfirst=True)

    # -------------------------------------------------------------------------
    # 2. Output database(s)
    # -------------------------------------------------------------------------

    pretty_names = []  # type: List[str]
    for processor in nlpdef.get_processors():
        if isinstance(processor, Cloud) and not processor.available_remotely:
            continue
        new_pretty_names = processor.make_tables(drop_first=not incremental)
        for npn in new_pretty_names:
            if npn in pretty_names:
                log.warning(f"An NLP processor has tried to re-make a table "
                            f"made by one of its colleagues: {npn}")
        pretty_names.extend(new_pretty_names)

    # -------------------------------------------------------------------------
    # 3. Delete WHERE NOT IN for incremental
    # -------------------------------------------------------------------------
    for ifconfig in nlpdef.get_ifconfigs():
        with MultiTimerContext(timer, TIMING_DELETE_WHERE_NO_SOURCE):
            if incremental:
                if not skipdelete:
                    delete_where_no_source(
                        nlpdef, ifconfig,
                        report_every=report_every,
                        chunksize=chunksize)
            else:  # full
                ifconfig.delete_all_progress_records()

    # -------------------------------------------------------------------------
    # 4. Overall commit (superfluous)
    # -------------------------------------------------------------------------
    nlpdef.commit_all()


# =============================================================================
# Core functions: local NLP
# =============================================================================

def process_nlp(nlpdef: NlpDefinition,
                incremental: bool = False,
                report_every: int = DEFAULT_REPORT_EVERY_NLP,
                tasknum: int = 0,
                ntasks: int = 1) -> None:
    """
    Main NLP processing function. Fetch text, send it to the NLP processor(s),
    storing the results, and make a note in the progress database.

    Args:
        nlpdef:
            :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
        incremental:
            incremental processing (skip previously processed records)
        report_every: report to the log every *n* source rows
        tasknum: which task number am I?
        ntasks: how many tasks are there in total?
    """
    log.info(SEP + "NLP")
    session = nlpdef.get_progdb_session()
    if not nlpdef.get_noncloud_processors():
        errmsg = (
            f"Can't use NLP definition {nlpdef.get_name()!r} as it has no "
            f"local processors (e.g. only has cloud processors). Specify the "
            f"cloud option to process via the cloud."
        )
        log.critical(errmsg)
        raise ValueError(errmsg)

    for ifconfig in nlpdef.get_ifconfigs():
        i = 0  # record count within this process
        recnum = tasknum  # record count overall
        totalcount = ifconfig.get_count()  # total number of records in table
        for text, other_values in ifconfig.gen_text(tasknum=tasknum,
                                                    ntasks=ntasks):
            log.debug(len(text))
            i += 1
            pkval = other_values[FN_SRCPKVAL]
            pkstr = other_values[FN_SRCPKSTR]
            if report_every and i % report_every == 0:
                log.info(
                    "Processing {db}.{t}.{c}, PK: {pkf}={pkv} "
                    "({overall}record {approx}{recnum}/{totalcount})"
                    "{thisproc}".format(
                        db=other_values[FN_SRCDB],
                        t=other_values[FN_SRCTABLE],
                        c=other_values[FN_SRCFIELD],
                        pkf=other_values[FN_SRCPKFIELD],
                        pkv=pkstr if pkstr else pkval,
                        overall="overall " if ntasks > 1 else "",
                        approx="~" if pkstr and ntasks > 1 else "",
                        # ... string hashing means approx. distribution
                        recnum=recnum + 1,
                        i=i,
                        totalcount=totalcount,
                        thisproc=(
                            " ({i}/~{proccount} this process)".format(
                                i=i,
                                proccount=totalcount // ntasks)
                            if ntasks > 1 else ""
                        )
                    )
                )
            recnum += ntasks
            # log.critical("other_values={}".format(repr(other_values)))
            srchash = nlpdef.hash(text)

            progrec = None
            if incremental:
                progrec = ifconfig.get_progress_record(pkval, pkstr)
                if progrec is not None:
                    if progrec.srchash == srchash:
                        log.debug("Record previously processed; skipping")
                        continue
                    else:
                        log.debug("Record has changed")
                else:
                    log.debug("Record is new")

            processor_failure = False
            for processor in nlpdef.get_noncloud_processors():
                if incremental:
                    processor.delete_dest_record(ifconfig, pkval, pkstr,
                                                 commit=incremental)
                try:
                    processor.process(text, other_values)
                except TextProcessingFailed:
                    processor_failure = True

            # If at least one processor failed, don't tell the progress
            # database that this record has been handled. That means that if
            # the administrator fixes this problem, this record will be
            # re-processed. (There may be some stray output from other,
            # successful, processors, but that will be deleted before
            # reprocessing in a subsequent incremental update.)
            if processor_failure:
                log.error(
                    f"At least one processor failed for this record "
                    f"(srctable={ifconfig.get_srctable()!r}, "
                    f"pkfield={ifconfig.get_srcpkfield()!r}, "
                    f"pkval={pkval!r}, pkstr={pkstr!r}); "
                    f"not marking it as processed.")
                continue

            # Make a note in the progress database that we've processed a
            # source record.
            truncated = other_values[TRUNCATED_FLAG]
            if not truncated or nlpdef.record_truncated_values:
                if progrec:  # modifying an existing record
                    progrec.whenprocessedutc = nlpdef.get_now()
                    progrec.srchash = srchash
                else:  # creating a new record
                    progrec = NlpRecord(
                        # Quasi-key fields:
                        srcdb=ifconfig.get_srcdb(),
                        srctable=ifconfig.get_srctable(),
                        srcpkval=pkval,
                        srcpkstr=pkstr,
                        srcfield=ifconfig.get_srcfield(),
                        nlpdef=nlpdef.get_name(),
                        # Other fields:
                        srcpkfield=ifconfig.get_srcpkfield(),
                        whenprocessedutc=nlpdef.get_now(),
                        srchash=srchash,
                    )
                    with MultiTimerContext(timer, TIMING_PROGRESS_DB_ADD):
                        session.add(progrec)

                # In incremental mode, do we commit immediately, because other
                # processes may need this table promptly... ?

                # force_commit = False  # definitely wrong; crashes as below
                # force_commit = incremental
                force_commit = ntasks > 1

                # - A single source record should not be processed by >1 CRATE
                #   process. So in theory there should be no conflicts.
                # - However, databases can lock in various ways. Can we
                #   guarantee it'll do something sensible?
                # - See also
                #   https://en.wikipedia.org/wiki/Isolation_(database_systems)
                #   http://skien.cc/blog/2014/02/06/sqlalchemy-and-race-conditions-follow-up/  # noqa
                #   http://docs.sqlalchemy.org/en/latest/core/connections.html?highlight=execution_options#sqlalchemy.engine.Connection.execution_options  # noqa
                # - However, empirically, setting this to False gives
                #   "Transaction (Process ID xx) was deadlocked on lock
                #   resources with another process and has been chosen as the
                #   deadlock victim. Rerun the transaction." -- with a SELECT
                #   query.
                # - SQL Server uses READ COMMITTED as the default isolation
                #   level.
                # - https://technet.microsoft.com/en-us/library/jj856598(v=sql.110).aspx  # noqa

                nlpdef.notify_transaction(
                    session=session, n_rows=1,
                    n_bytes=sys.getsizeof(progrec),  # approx
                    force_commit=force_commit)

    nlpdef.commit_all()


# =============================================================================
# Core functions: cloud NLP
# =============================================================================

def send_cloud_requests(
        generated_text: Generator[Tuple[str, Dict[str, Any]], None, None],
        crinfo: CloudRunInfo,
        ifconfig: InputFieldConfig,
        global_recnum: int,
        report_every: int = DEFAULT_REPORT_EVERY_NLP,
        incremental: bool = False,
        queue: bool = True) -> Tuple[List[CloudRequestProcess], bool, int]:
    """
    Sends off a series of cloud requests and returns them as a list.
    'queue' determines whether these are queued requests or not. Also returns
    whether the generator for the text is empty.
    """
    requests = []  # type: List[CloudRequestProcess]
    cookies = None  # type: Optional[CookieJar]
    i = 1  # number of requests sent
    totalcount = ifconfig.get_count()  # total number of records in table
    # Check processors are available
    available_procs = crinfo.get_remote_processors()
    if not available_procs:  # request failed, or no processors available
        return [], False, global_recnum
    cloudcfg = crinfo.cloudcfg
    cloud_request = CloudRequestProcess(crinfo=crinfo)
    empty_request = True
    number_of_records = cloudcfg.max_records_per_request
    limit_before_commit = cloudcfg.limit_before_commit
    recs = 0
    hasher = crinfo.nlpdef.hash
    for text, other_values in generated_text:
        global_recnum += 1
        pkval = other_values[FN_SRCPKVAL]
        pkstr = other_values[FN_SRCPKSTR]
        if report_every and global_recnum % report_every == 0:
            log.info(
                "Processing {db}.{t}.{c}, PK: {pkf}={pkv} "
                "(record {g_recnum}/{totalcount})".format(
                    db=other_values[FN_SRCDB],
                    t=other_values[FN_SRCTABLE],
                    c=other_values[FN_SRCFIELD],
                    pkf=other_values[FN_SRCPKFIELD],
                    pkv=pkstr if pkstr else pkval,
                    g_recnum=global_recnum,
                    totalcount=totalcount
                )
            )
        # log.critical("other_values={}".format(repr(other_values)))
        srchash = hasher(text)
        if incremental:
            progrec = ifconfig.get_progress_record(pkval, pkstr)
            if progrec is not None:
                if progrec.srchash == srchash:
                    log.debug("Record previously processed; skipping")
                    continue
                else:
                    log.debug("Record has changed")
            else:
                log.debug("Record is new")

        # Add the text to the cloud request with the appropriate metadata
        success = cloud_request.add_text(text, other_values)
        recs += 1
        if success:
            empty_request = False
        else:
            if not empty_request:
                cloud_request.send_process_request(
                    queue=queue,
                    cookies=cookies,
                    include_text_in_reply=crinfo.cloudcfg.has_gate_processors  # noqa
                )
                # If there's a connection error, we only get this far if we
                # didn't choose to stop at failure
                if cloud_request.request_failed:
                    log.warning("Continuing after failed request.")
                else:
                    if cloud_request.cookies:
                        cookies = cloud_request.cookies
                    log.info(f"Sent request to be processed: #{i} of this "
                             "block")
                    i += 1
                    requests.append(cloud_request)
            cloud_request = CloudRequestProcess(crinfo=crinfo)
            # Is the text too big on its own? If so, don't send it. Otherwise
            # add it to the new request
            text_too_big = not cloud_request.add_text(text, other_values)
            if text_too_big:
                log.warning("Skipping text that's too long to send")
            empty_request = text_too_big

        # Add 'srchash' to 'other_values' so the metadata will contain it
        # and we can use it later on for updating the progress database
        other_values[FN_SRCHASH] = srchash

        # If we've reached the limit of records before commit, return to
        # outer function in order to process and commit (or write to file if
        # it's a queued request)
        if recs >= limit_before_commit - 1:
            break

    if not empty_request:
        # Send last request
        cloud_request.send_process_request(
            queue=queue, cookies=cookies,
            include_text_in_reply=cloudcfg.has_gate_processors)
        if cloud_request.request_failed:
            log.warning("Continuing after failed request.")
        else:
            log.info(f"Sent request to be processed: #{i} of this block")
            requests.append(cloud_request)
    # Return the cloud request objects, whether any records have
    # been processed and the global record number
    return requests, recs > 0, global_recnum


def process_cloud_nlp(crinfo: CloudRunInfo,
                      incremental: bool = False,
                      report_every: int = DEFAULT_REPORT_EVERY_NLP) -> None:
    """
    Process text by sending it off to the cloud processors in queued mode.
    """
    log.info(SEP + "NLP")
    nlpdef = crinfo.nlpdef
    filename = crinfo.cloudcfg.data_filename()
    # Start with blank file
    open(filename, 'w').close()
    # Use append so that, if there's a problem part-way through, we don't lose
    # all data
    with open(filename, 'a') as request_data:
        for ifconfig in nlpdef.get_ifconfigs():
            generated_text = ifconfig.gen_text()
            global_recnum = 0  # Global record number within this ifconfig
            # start = 0  # Start for first block
            # total = ifconfig.get_count()
            records_left = True
            while records_left:
                cloud_requests, records_left, global_recnum = send_cloud_requests(  # noqa
                    generated_text=generated_text,
                    crinfo=crinfo,
                    ifconfig=ifconfig,
                    # start_record=start,
                    global_recnum=global_recnum,
                    incremental=incremental,
                    report_every=report_every)
                for cloud_request in cloud_requests:
                    if cloud_request.queue_id:
                        request_data.write(
                            f"{ifconfig.section},{cloud_request.queue_id}\n")
                    else:
                        log.warning("Sent request does not contain queue_id.")
                # start += crinfo.cloudcfg.limit_before_commit


def retrieve_nlp_data(crinfo: CloudRunInfo,
                      incremental: bool = False) -> None:
    """
    Try to retrieve the data from the cloud processors.
    """
    nlpdef = crinfo.nlpdef
    session = nlpdef.get_progdb_session()
    cloudcfg = crinfo.cloudcfg
    filename = cloudcfg.data_filename()
    if not os.path.exists(filename):
        log.error(f"File {filename!r} does not exist. "
                  f"Request may not have been sent.")
        raise FileNotFoundError
    with open(filename, 'r') as request_data:
        reqdata = request_data.readlines()
    i = 1  # number of requests
    cookies = None  # type: Optional[CookieJar]
    # with open(filename, 'w') as request_data:
    remaining_data = []  # type: List[str]
    ifconfig_cache = {}  # type: Dict[str, InputFieldConfig]
    all_ready = True  # not necessarily true, but need for later
    count = 0  # count of records before a write to the database
    uncommitted_data = False
    for line in reqdata:
        # Are there are records (whether ready or not) associated with
        # the queue_id
        records_exist = False
        if_section, queue_id = line.strip().split(',')
        if if_section in ifconfig_cache:
            ifconfig = ifconfig_cache[if_section]
        else:
            ifconfig = InputFieldConfig(nlpdef=nlpdef, section=if_section)
            ifconfig_cache[if_section] = ifconfig
        seen_srchashs = []  # type: List[str]
        cloud_request = CloudRequestProcess(crinfo=crinfo)
        # cloud_request.set_mirror_processors(mirror_procs)
        cloud_request.set_queue_id(queue_id)
        log.info(f"Atempting to retrieve data from request #{i} ...")
        i += 1
        ready = cloud_request.check_if_ready(cookies)
        if cloud_request.cookies:
            cookies = cloud_request.cookies

        if not ready:
            # If results are not ready for this particular queue_id, put
            # back in file
            # request_data.write(f"{if_section},{queue_id}\n")
            remaining_data.append(f"{if_section},{queue_id}\n")
            all_ready = False
        else:
            nlp_data = cloud_request.nlp_data
            for result in nlp_data[NKeys.RESULTS]:
                # There are records associated with the given queue_id
                records_exist = True
                uncommitted_data = True
                # 'metadata' is just 'other_values' from before
                metadata = result[NKeys.METADATA]
                pkval = metadata[FN_SRCPKVAL]
                pkstr = metadata[FN_SRCPKSTR]
                srchash = metadata[FN_SRCHASH]
                progrec = None
                if incremental:
                    progrec = ifconfig.get_progress_record(pkval, pkstr)
                    crinfo.delete_dest_records(ifconfig, pkval, pkstr,
                                               commit=True)
                elif srchash in seen_srchashs:
                    progrec = ifconfig.get_progress_record(pkval, pkstr)
                seen_srchashs.append(srchash)
                # Make a note in the progress database that we've processed
                # a source record
                if progrec:  # modifying an existing record
                    progrec.whenprocessedutc = nlpdef.get_now()
                    progrec.srchash = srchash
                else:  # creating a new record
                    progrec = NlpRecord(
                        # Quasi-key fields:
                        srcdb=ifconfig.get_srcdb(),
                        srctable=ifconfig.get_srctable(),
                        srcpkval=pkval,
                        srcpkstr=pkstr,
                        srcfield=ifconfig.get_srcfield(),
                        nlpdef=nlpdef.get_name(),
                        # Other fields:
                        srcpkfield=ifconfig.get_srcpkfield(),
                        whenprocessedutc=nlpdef.get_now(),
                        srchash=srchash,
                    )
                    with MultiTimerContext(timer, TIMING_PROGRESS_DB_ADD):
                        session.add(progrec)
                count += 1
            if records_exist:
                log.info("Request ready.")
                cloud_request.process_all()
                if count >= cloudcfg.limit_before_commit:
                    nlpdef.commit_all()
                    count = 0
                    uncommitted_data = False
            else:
                log.warning(f"No records found for queue_id {queue_id}.")
    if uncommitted_data:
        nlpdef.commit_all()
    if all_ready:
        os.remove(filename)
    else:
        # Put this here to avoid losing the queue_ids if something goes wrong
        with open(filename, 'w') as request_data:
            for data in remaining_data:
                request_data.write(data)
        log.info("There are still results to be processed. Re-run this "
                 "command later to retrieve them.")


# @do_cprofile
def process_cloud_now(
        crinfo: CloudRunInfo,
        incremental: bool = False,
        report_every: int = DEFAULT_REPORT_EVERY_NLP) -> None:
    """
    Process text by sending it off to the cloud processors in non-queued mode.
    """
    nlpdef = crinfo.nlpdef
    session = nlpdef.get_progdb_session()
    for ifconfig in nlpdef.get_ifconfigs():
        global_recnum = 0  # Global record number within this ifconfig
        seen_srchashs = []  # type: List[str]
        # total = ifconfig.get_count()
        generated_text = ifconfig.gen_text()
        records_left = True
        while records_left:
            cloud_requests,  records_left, global_recnum = send_cloud_requests(
                generated_text=generated_text,
                crinfo=crinfo,
                global_recnum=global_recnum,
                ifconfig=ifconfig,
                incremental=incremental,
                report_every=report_every,
                queue=False
            )
            for cloud_request in cloud_requests:
                if cloud_request.request_failed:
                    continue
                # cloud_request.set_mirror_processors(mirror_procs)
                cloud_request.process_all()
                nlp_data = cloud_request.nlp_data
                for result in nlp_data[NKeys.RESULTS]:
                    # 'metadata' is just 'other_values' from before
                    metadata = result[NKeys.METADATA]
                    pkval = metadata[FN_SRCPKVAL]
                    pkstr = metadata[FN_SRCPKSTR]
                    srchash = metadata[FN_SRCHASH]
                    progrec = None
                    if incremental:
                        crinfo.delete_dest_records(ifconfig, pkval, pkstr,
                                                   commit=True)
                        # Record progress in progress database
                        progrec = ifconfig.get_progress_record(pkval, pkstr)
                    # Check that we haven't already done the progrec for this
                    # record to avoid clashes - it's possible as each processor
                    # may contain results for each record and a set of results
                    # is a list of processors and their results
                    if srchash in seen_srchashs:
                        progrec = ifconfig.get_progress_record(pkval, pkstr)
                    seen_srchashs.append(srchash)
                    # Make a note in the progress database that we've processed
                    # a source record
                    if progrec:  # modifying an existing record
                        progrec.whenprocessedutc = nlpdef.get_now()
                        progrec.srchash = srchash
                    else:  # creating a new record
                        progrec = NlpRecord(
                            # Quasi-key fields:
                            srcdb=ifconfig.get_srcdb(),
                            srctable=ifconfig.get_srctable(),
                            srcpkval=pkval,
                            srcpkstr=pkstr,
                            srcfield=ifconfig.get_srcfield(),
                            nlpdef=nlpdef.get_name(),
                            # Other fields:
                            srcpkfield=ifconfig.get_srcpkfield(),
                            whenprocessedutc=nlpdef.get_now(),
                            srchash=srchash,
                        )
                        with MultiTimerContext(timer, TIMING_PROGRESS_DB_ADD):
                            session.add(progrec)
            session.commit()


    nlpdef.commit_all()


def cancel_request(nlpdef: NlpDefinition, cancel_all: bool = False) -> None:
    """
    Delete pending requests from the server's queue.
    """
    nlpname = nlpdef.get_name()
    cloudcfg = nlpdef.get_cloud_config_or_raise()
    cloud_request = CloudRequestQueueManagement(nlpdef=nlpdef)

    if cancel_all:
        # Deleting all from queue!
        cloud_request.delete_all_from_queue()
        log.info(f"All cloud requests cancelled.")
        # Should the files be deleted in the program or is that dangerous?
        # ... OK now we guarantee that CRATE will create and use a specific
        # directory.
        purge(cloudcfg.req_data_dir, "*")
        return
    # Otherwise:

    filename = cloudcfg.data_filename()
    if not os.path.exists(filename):
        log.error(f"File {filename!r} does not exist. "
                  f"Request may not have been sent.")
        raise FileNotFoundError
    queue_ids = []  # type: List[str]
    with open(filename, 'r') as request_data:
        reqdata = request_data.readlines()
        for line in reqdata:
            if_section, queue_id = line.strip().split(',')
            queue_ids.append(queue_id)
    cloud_request.delete_from_queue(queue_ids)
    # Remove the file with the request info
    os.remove(filename)
    log.info(f"Cloud request for nlp definition {nlpname} cancelled.")


def show_cloud_queue(nlpdef: NlpDefinition) -> None:
    """
    Get list of the user's queued requests and print to screen.
    """
    cloud_request = CloudRequestQueueManagement(nlpdef=nlpdef)
    queue = cloud_request.show_queue()
    if not queue:
        log.info("No requests in queue.")
        return
    writer = None
    for entry in queue:
        if writer is None:  # first line
            writer = csv.DictWriter(sys.stdout, fieldnames=entry.keys())
            writer.writeheader()
        writer.writerow(entry)


def print_cloud_processors(nlpdef: NlpDefinition,
                           indent: int = 4,
                           sort_keys: bool = True) -> None:
    """
    Print remote processor definitions to the screen.
    """
    cloud_request = CloudRequestListProcessors(nlpdef=nlpdef)
    procs = cloud_request.get_remote_processors()
    asdictlist = [p.infodict for p in procs]
    text = json.dumps(asdictlist, indent=indent, sort_keys=sort_keys)
    print(text)


# =============================================================================
# Database info
# =============================================================================

def show_source_counts(nlpdef: NlpDefinition) -> None:
    """
    Print (to stdout) the number of records in all source tables.

    Args:
        nlpdef:
            :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
    """
    print("SOURCE TABLE RECORD COUNTS:")
    counts = []  # type: List[Tuple[str, int]]
    for ifconfig in nlpdef.get_ifconfigs():
        session = ifconfig.get_source_session()
        dbname = ifconfig.get_srcdb()
        tablename = ifconfig.get_srctable()
        n = count_star(session, tablename)
        counts.append((f"{dbname}.{tablename}", n))
    print_record_counts(counts)


def show_dest_counts(nlpdef: NlpDefinition) -> None:
    """
    Print (to stdout) the number of records in all destination tables.

    Args:
        nlpdef:
            :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
    """
    print("DESTINATION TABLE RECORD COUNTS:")
    counts = []  # type: List[Tuple[str, int]]
    for processor in nlpdef.get_processors():
        session = processor.get_session()
        dbname = processor.get_dbname()
        for tablename in processor.get_tablenames():
            n = count_star(session, tablename)
            counts.append((f"DESTINATION: {dbname}.{tablename}", n))
    print_record_counts(counts)


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    """
    Command-line entry point. See command-line help.
    """
    version = f"Version {CRATE_VERSION} ({CRATE_VERSION_DATE})"
    description = f"NLP manager. {version}. By Rudolf Cardinal."

    # todo: better with a subcommand parser?

    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--version", action="version", version=version)
    parser.add_argument(
        "--config",
        help=f"Config file (overriding environment variable "
             f"{NLP_CONFIG_ENV_VAR})")
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help="Be verbose (use twice for extra verbosity)")
    parser.add_argument(
        "--nlpdef", nargs="?", default=None,
        help="NLP definition name (from config file)")
    parser.add_argument(
        '--report_every_fast', nargs="?", type=int,
        default=DEFAULT_REPORT_EVERY,
        help=f"Report insert progress (for fast operations) every n rows in "
             f"verbose mode (default {DEFAULT_REPORT_EVERY})")
    parser.add_argument(
        '--report_every_nlp', nargs="?", type=int,
        default=DEFAULT_REPORT_EVERY_NLP,
        help=f"Report progress for NLP every n rows in verbose mode "
             f"(default {DEFAULT_REPORT_EVERY_NLP})")
    parser.add_argument(
        '--chunksize', nargs="?", type=int,
        default=DEFAULT_CHUNKSIZE,
        help=f"Number of records copied in a chunk when copying PKs from one "
             f"database to another (default {DEFAULT_CHUNKSIZE})")
    parser.add_argument(
        "--process", nargs="?", type=int, default=0,
        help="For multiprocess mode: specify process number")
    parser.add_argument(
        "--nprocesses", nargs="?", type=int, default=1,
        help="For multiprocess mode: specify total number of processes "
             "(launched somehow, of which this is to be one)")
    parser.add_argument(
        "--processcluster", default="",
        help="Process cluster name")
    parser.add_argument(
        "--democonfig", action="store_true",
        help="Print a demo config file")
    parser.add_argument(
        "--listprocessors", action="store_true",
        help="Show possible built-in NLP processor names")
    parser.add_argument(
        "--describeprocessors", action="store_true",
        help="Show details of built-in NLP processors")
    parser.add_argument(
        "--print_local_processors", action="store_true",
        help="Show NLPRP JSON for local processors that are part of the "
             "chosen NLP definition, then stop")
    parser.add_argument(
        "--print_cloud_processors", action="store_true",
        help="Show NLPRP JSON for cloud (remote) processors that are part of "
             "the chosen NLP definition, then stop")
    parser.add_argument(
        "--showinfo", required=False, nargs='?',
        metavar="NLP_CLASS_NAME",
        help="Show detailed information for a parser")
    parser.add_argument(
        "--count", action="store_true",
        help="Count records in source/destination databases, then stop")

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "-i", "--incremental", dest="incremental", action="store_true",
        help="Process only new/changed information, where possible "
             "(* default)")
    mode_group.add_argument(
        "-f", "--full", dest="incremental", action="store_false",
        help="Drop and remake everything")
    parser.set_defaults(incremental=True)

    parser.add_argument(
        "--dropremake", action="store_true",
        help="Drop/remake destination tables only")
    parser.add_argument(
        "--skipdelete", dest="skipdelete", action="store_true",
        help="For incremental updates, skip deletion of rows "
             "present in the destination but not the source")
    parser.add_argument(
        "--nlp", action="store_true",
        help="Perform NLP processing only")
    parser.add_argument(
        "--echo", action="store_true",
        help="Echo SQL")
    parser.add_argument(
        "--timing", action="store_true",
        help="Show detailed timing breakdown")
    parser.add_argument(
        "--cloud", action="store_true",
        help="Use cloud-based NLP processing tools. Queued mode by default.")
    parser.add_argument(
        "--immediate", action="store_true",
        help="To be used with 'cloud'. Process immediately.")
    parser.add_argument(
        "--retrieve", action="store_true",
        help="Retrieve NLP data from cloud")
    parser.add_argument(
        "--cancelrequest", action="store_true",
        help="Cancel pending requests for the nlpdef specified")
    parser.add_argument(
        "--cancelall", action="store_true",
        help="Cancel all pending cloud requests. WARNING: this option "
             "cancels all pending requests - not just those for the nlp "
             "definition specified")
    parser.add_argument(
        "--showqueue", action="store_true",
        help="Shows all pending cloud requests.")
    args = parser.parse_args()

    # Validate args
    if args.nprocesses < 1:
        raise ValueError("--nprocesses must be >=1")
    if args.process < 0 or args.process >= args.nprocesses:
        raise ValueError(
            "--process argument must be from 0 to (nprocesses - 1) inclusive")
    if args.config:
        os.environ[NLP_CONFIG_ENV_VAR] = args.config
    if args.cloud and args.retrieve:
        raise ValueError(
            "--cloud and --retrieve cannot be used together")

    # Verbosity and logging
    mynames = []  # type: List[str]
    if args.processcluster:
        mynames.append(args.processcluster)
    if args.nprocesses > 1:
        mynames.append(f"proc{args.process}")
    loglevel = logging.DEBUG if args.verbose else logging.INFO
    rootlogger = logging.getLogger()
    configure_logger_for_colour(rootlogger, level=loglevel, extranames=mynames)

    # -------------------------------------------------------------------------

    # Demo config?
    if args.democonfig:
        print(demo_nlp_config())
        return

    # List or describe processors?
    if args.listprocessors:
        print("\n".join(possible_processor_names()))
        return
    if args.describeprocessors:
        print(possible_processor_table())
        return
    if args.showinfo:
        parser = make_nlp_parser_unconfigured(args.showinfo,
                                              raise_if_absent=False)
        if parser:
            print(f"Info for class {args.showinfo}:\n")
            parser.print_info()
        else:
            print(f"No such processor class: {args.showinfo}")
        return

    # Otherwise, we need a valid NLP definition.
    if args.nlpdef is None:
        raise ValueError(
            "Must specify nlpdef parameter (unless --democonfig, "
            "--listprocessors, or --describeprocessors used)")

    everything = not any([args.dropremake, args.nlp])

    # Report args
    log.debug(f"arguments: {args}")

    # Load/validate config
    nlpdef = NlpDefinition(args.nlpdef,
                           logtag="_".join(mynames).replace(" ", "_"))
    nlpdef.set_echo(args.echo)

    # Count only?
    if args.count:
        show_source_counts(nlpdef)
        show_dest_counts(nlpdef)
        return

    # Show configured processor definitions only?
    if args.print_local_processors:
        print(nlpdef.nlprp_local_processors_json())
        return
    if args.print_cloud_processors:
        print_cloud_processors(nlpdef)
        return

    # -------------------------------------------------------------------------

    # Delete from queue - do this before Drop/Remake and return so we don't
    # drop all the tables just to cancel the request
    # Same for 'showqueue'. All of these need config as they require url etc.
    if args.cancelrequest:
        cancel_request(nlpdef)
        return
    if args.cancelall:
        cancel_request(nlpdef, cancel_all=args.cancelall)
        return
    if args.showqueue:
        show_cloud_queue(nlpdef)
        return

    crinfo = None  # type: Optional[CloudRunInfo]  # for type checker!
    if args.cloud or args.retrieve:
        # Set appropriate things for cloud - need to do this before
        # drop_remake, but after cancel_request or show_cloud_queue to avoid
        # unecessary requests
        cloudcfg = nlpdef.get_cloud_config_or_raise()
        CloudRequest.set_rate_limit(cloudcfg.rate_limit_hz)
        crinfo = CloudRunInfo(nlpdef)

    log.info(f"Starting: incremental={args.incremental}")
    start = get_now_utc_pendulum()
    timer.set_timing(args.timing, reset=True)

    # 1. Drop/remake tables. Single-tasking only.
    with MultiTimerContext(timer, TIMING_DROP_REMAKE):
        if args.dropremake or everything:
            drop_remake(nlpdef,
                        incremental=args.incremental,
                        skipdelete=args.skipdelete,
                        report_every=args.report_every_fast,
                        chunksize=args.chunksize)

    # From here, in a multiprocessing environment, trap any errors simply so
    # we can report the process number clearly.

    # 2. NLP
    if args.nlp or everything:
        try:
            if args.cloud:
                if args.immediate:
                    process_cloud_now(
                        crinfo,
                        incremental=args.incremental,
                        report_every=args.report_every_nlp)
                else:
                    process_cloud_nlp(crinfo,
                                      incremental=args.incremental,
                                      report_every=args.report_every_nlp)
            elif args.retrieve:
                retrieve_nlp_data(crinfo,
                                  incremental=args.incremental)
            else:
                process_nlp(nlpdef,
                            incremental=args.incremental,
                            report_every=args.report_every_nlp,
                            tasknum=args.process,
                            ntasks=args.nprocesses)
        except Exception as exc:
            log.critical("TERMINAL ERROR FROM THIS PROCESS")  # so we see proc#
            die(exc)

    log.info("Finished")
    end = get_now_utc_pendulum()
    time_taken = end - start
    log.info(f"Time taken: {time_taken.total_seconds():.3f} seconds")

    if args.timing:
        timer.report()


# =============================================================================
# Command-line entry point
# =============================================================================

if __name__ == '__main__':
    main()
