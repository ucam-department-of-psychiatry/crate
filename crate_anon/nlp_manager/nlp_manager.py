#!/usr/bin/env python

"""
crate_anon/nlp_manager/nlp_manager.py

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

.. todo:: comments for NLP output fields (in table definition, destfields)

"""  # noqa


# =============================================================================
# Imports
# =============================================================================

import argparse
import logging
import os
import sys
from typing import Any, Dict, List, Tuple

from cardinal_pythonlib.datetimefunc import get_now_utc_pendulum
from cardinal_pythonlib.exceptions import die
from cardinal_pythonlib.logs import configure_logger_for_colour
from cardinal_pythonlib.sqlalchemy.core_query import count_star
from cardinal_pythonlib.timing import MultiTimerContext, timer
from sqlalchemy.schema import Column, Index, Table
from sqlalchemy.types import BigInteger, String

from crate_anon.anonymise.constants import (
    DEFAULT_CHUNKSIZE,
    DEFAULT_REPORT_EVERY,
    TABLE_KWARGS,
    SEP,
)
from crate_anon.common.formatting import print_record_counts
from crate_anon.nlp_manager.all_processors import (
    get_nlp_parser_debug_instance,
    possible_processor_names,
    possible_processor_table,
)
from crate_anon.nlp_manager.constants import (
    DEFAULT_REPORT_EVERY_NLP,
    DEMO_CONFIG,
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
)
from crate_anon.nlp_manager.models import FN_SRCHASH, NlpRecord
from crate_anon.nlp_manager.nlp_definition import NlpDefinition
from crate_anon.nlp_manager.cloud_parser import CloudRequest, CloudNlpConfigKeys
from crate_anon.nlprp.constants import NlprpKeys as NKeys
from crate_anon.version import CRATE_VERSION, CRATE_VERSION_DATE

log = logging.getLogger(__name__)

TIMING_DROP_REMAKE = "drop_remake"
TIMING_DELETE_WHERE_NO_SOURCE = "delete_where_no_source"
TIMING_PROGRESS_DB_ADD = "progress_db_add"

CLOUD_NLP_SECTION = "Cloud_NLP"


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

    def insert(records_):
        n_rows = len(records_)
        log.debug(f"... inserting {n_rows} records")
        for db in databases:
            session_ = db['session']
            temptable_ = db['temptable']  # type: Table
            session_.execute(temptable_.insert(), records_)
            nlpdef.notify_transaction(session_, n_rows=n_rows,
                                      n_bytes=sys.getsizeof(records_))

    def commit():
        for db in databases:
            nlpdef.commit(db['session'])

    # -------------------------------------------------------------------------
    # Main code
    # -------------------------------------------------------------------------
    # Use info log level, otherwise it looks like our code hangs with very
    # large databases.

    log.info(f"delete_where_no_source: examining source table "
             f"{ifconfig.get_srcdb()}.{ifconfig.get_srctable()}; MAY BE SLOW")

    # Start our list with the progress database
    databases = [{
        'session': nlpdef.get_progdb_session(),
        'engine': nlpdef.get_progdb_engine(),
        'metadata': nlpdef.get_progdb_metadata(),
        'db': nlpdef.get_progdb(),
        'temptable': None,  # type: Table
    }]

    # Add the processors' destination databases
    for processor in nlpdef.get_processors():  # of type BaseNlpParser
        session = processor.get_session()
        if any(x['session'] == session for x in databases):
            continue  # already exists
        databases.append({
            'session': session,
            'engine': processor.get_engine(),
            'metadata': processor.get_metadata(),
            'db': processor.get_destdb(),
        })

    # Make a temporary table in each database (note: the Table objects become
    # affiliated to their engine, I think, so make separate ones for each).
    log.info(f"... using {len(databases)} destination database(s)")
    log.info("... dropping (if exists) and creating temporary table(s)")
    for database in databases:
        engine = database['engine']
        temptable = Table(
            nlpdef.get_temporary_tablename(),
            database['metadata'],
            Column(FN_SRCPKVAL, BigInteger),  # not PK, as may be a hash
            Column(FN_SRCPKSTR, String(MAX_STRING_PK_LENGTH)),
            **TABLE_KWARGS
        )
        temptable.drop(engine, checkfirst=True)
        temptable.create(engine, checkfirst=True)
        database['temptable'] = temptable

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
        temptable = database['temptable']  # type: Table
        index = Index('_temptable_idx', temptable.columns[FN_SRCPKVAL])
        index.create(database['engine'])

    # DELETE FROM desttable WHERE destpk NOT IN (SELECT srcpk FROM temptable)
    log.info("... deleting from progress/destination DBs where appropriate")

    # Delete from progress database
    prog_db = databases[0]
    prog_temptable = prog_db['temptable']
    ifconfig.delete_progress_records_where_srcpk_not(prog_temptable)

    # Delete from others
    for processor in nlpdef.get_processors():
        database = [x for x in databases
                    if x['session'] == processor.get_session()][0]
        temptable = database['temptable']
        processor.delete_where_srcpk_not(ifconfig, temptable)

    # Drop temporary tables
    log.info("... dropping temporary table(s)")
    for database in databases:
        database['temptable'].drop(database['engine'], checkfirst=True)

    # Commit
    commit()

    # Update metadata to reflect the fact that the temporary tables have been
    # dropped
    for database in databases:
        database['db'].update_metadata()


# =============================================================================
# Core functions
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
    for ifconfig in nlpdef.get_ifconfigs():
        i = 0  # record count within this process
        recnum = tasknum  # record count overall
        totalcount = ifconfig.get_count()  # total number of records in table
        for text, other_values in ifconfig.gen_text(tasknum=tasknum,
                                                    ntasks=ntasks):
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

            for processor in nlpdef.get_processors():
                if incremental:
                    processor.delete_dest_record(ifconfig, pkval, pkstr,
                                                 commit=incremental)
                processor.process(text, other_values)

            # Make a note in the progress database that we've processed a
            # source record.
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
            # - However, databases can lock in various ways. Can we guarantee
            #   it'll do something sensible?
            # - See also
            #   https://en.wikipedia.org/wiki/Isolation_(database_systems)
            #   http://skien.cc/blog/2014/02/06/sqlalchemy-and-race-conditions-follow-up/  # noqa
            #   http://docs.sqlalchemy.org/en/latest/core/connections.html?highlight=execution_options#sqlalchemy.engine.Connection.execution_options  # noqa
            # - However, empirically, setting this to False gives
            #   "Transaction (Process ID xx) was deadlocked on lock resources
            #   with another process and has been chosen as the deadlock
            #   victim. Rerun the transaction." -- with a SELECT query.
            # - SQL Server uses READ COMMITTED as the default isolation level.
            # - https://technet.microsoft.com/en-us/library/jj856598(v=sql.110).aspx  # noqa

            nlpdef.notify_transaction(session=session, n_rows=1,
                                      n_bytes=sys.getsizeof(progrec),  # approx
                                      force_commit=force_commit)

    nlpdef.commit_all()


def send_cloud_requests(
        nlpdef: NlpDefinition,
        ifconfig: InputFieldConfig,
        url: str,
        username: str,
        password: str,
        max_length: int = 0,
        report_every: int = DEFAULT_REPORT_EVERY_NLP,
        incremental: bool = False,
        queue: bool = True,
        verify_ssl: bool = True) -> List[CloudRequest]:
    """
    Sends off a series of cloud requests and returns them as a list.
    'queue' determines whether these are queued requests or not.
    """
    requests = []
    recnum = 0
    cookies = None
    i = 1  # number of requests sent
    totalcount = ifconfig.get_count()  # total number of records in table
    # Check processors are available
    available_procs = CloudRequest.list_processors(url,
                                                   username,
                                                   password,
                                                   verify_ssl)
    cloud_request = CloudRequest(nlpdef=nlpdef,
                                 url=url,
                                 username=username,
                                 password=password,
                                 max_length=max_length,
                                 allowable_procs=available_procs,
                                 verify_ssl=verify_ssl)
    empty_request = True
    for text, other_values in ifconfig.gen_text():
        pkval = other_values[FN_SRCPKVAL]
        pkstr = other_values[FN_SRCPKSTR]
        recnum += 1
        if report_every and recnum % report_every == 0:
            log.info(
                "Processing {db}.{t}.{c}, PK: {pkf}={pkv} "
                "(record {recnum}/{totalcount})".format(
                    db=other_values[FN_SRCDB],
                    t=other_values[FN_SRCTABLE],
                    c=other_values[FN_SRCFIELD],
                    pkf=other_values[FN_SRCPKFIELD],
                    pkv=pkstr if pkstr else pkval,
                    recnum=recnum + 1,
                    totalcount=totalcount
                )
            )
        # log.critical("other_values={}".format(repr(other_values)))
        srchash = nlpdef.hash(text)
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
        if success:
            empty_request = False
        else:
            if not empty_request:
                cloud_request.send_process_request(queue, cookies)
                if cloud_request.cookies:
                    cookies = cloud_request.cookies
                log.info(f"Sent request to be processed: #{i}")
                i += 1
                requests.append(cloud_request)
            cloud_request = CloudRequest(
                nlpdef=nlpdef,
                url=url,
                username=username,
                password=password,
                max_length=max_length,
                allowable_procs=available_procs,
                verify_ssl=verify_ssl)
            empty_request = True
            # Is the text too big on its own? If so, don't send it. Otherwise
            # add it to the new request
            text_too_big = not cloud_request.add_text(text, other_values)
            if text_too_big:
                log.warning(
                    "Record {db}.{t}.{c}, PK: {pkf}={pkv} "
                    "is too big to send".format(
                        db=other_values[FN_SRCDB],
                        t=other_values[FN_SRCTABLE],
                        c=other_values[FN_SRCFIELD],
                        pkf=other_values[FN_SRCPKFIELD],
                        pkv=pkstr if pkstr else pkval,
                        recnum=recnum + 1,
                        totalcount=totalcount
                    )
                )
            else:
                empty_request = False

        # Add 'srchash' to 'other_values' so the metadata will contain it
        # and we can use it later on for updating the progress database
        other_values[FN_SRCHASH] = srchash
    if not empty_request:
        # Send last request
        cloud_request.send_process_request(queue, cookies)
        log.info(f"Sent request to be processed: #{i}")
        requests.append(cloud_request)
    return requests


def process_cloud_nlp(nlpdef: NlpDefinition,
                      incremental: bool = False,
                      report_every: int = DEFAULT_REPORT_EVERY_NLP,
                      verify_ssl: bool = True) -> None:
    """
    Process text by sending it off to the cloud processors in queued mode.
    """
    log.info(SEP + "NLP")
    nlpname = nlpdef.get_name()
    config = nlpdef.get_parser()
    req_data_dir = config.get_str(section=CLOUD_NLP_SECTION,
                                  option=CloudNlpConfigKeys.REQUEST_DATA_DIR,
                                  required=True)
    url = config.get_str(section=CLOUD_NLP_SECTION,
                         option=CloudNlpConfigKeys.URL,
                         required=True)
    username = config.get_str(section=CLOUD_NLP_SECTION,
                              option=CloudNlpConfigKeys.USERNAME,
                              default="")
    password = config.get_str(section=CLOUD_NLP_SECTION,
                              option=CloudNlpConfigKeys.PASSWORD,
                              default="")
    max_length = config.get_int_default_if_failure(
                     section=CLOUD_NLP_SECTION,
                     option=CloudNlpConfigKeys.MAX_LENGTH,
                     default=0)
    with open(f'{req_data_dir}/request_data_{nlpname}.txt', 'w') as request_data:  # noqa
        for ifconfig in nlpdef.get_ifconfigs():
            cloud_requests = send_cloud_requests(
                nlpdef=nlpdef,
                ifconfig=ifconfig,
                url=url,
                username=username,
                password=password,
                max_length=max_length,
                incremental=incremental,
                report_every=report_every,
                verify_ssl=verify_ssl)
            for cloud_request in cloud_requests:
                if cloud_request.queue_id:
                    request_data.write(
                        f"{ifconfig.section},{cloud_request.queue_id}\n")
                else:
                    log.warning("Sent request does not contain queue_id.")


def retrieve_nlp_data(nlpdef: NlpDefinition,
                      incremental: bool = False,
                      verify_ssl: bool = True) -> None:
    """
    Try to retrieve the data from the cloud processors.
    """
    session = nlpdef.get_progdb_session()
    nlpname = nlpdef.get_name()
    config = nlpdef.get_parser()
    req_data_dir = config.get_str(section=CLOUD_NLP_SECTION,
                                  option=CloudNlpConfigKeys.REQUEST_DATA_DIR,
                                  required=True)
    url = config.get_str(section=CLOUD_NLP_SECTION,
                         option=CloudNlpConfigKeys.URL,
                         required=True)
    username = config.get_str(section=CLOUD_NLP_SECTION,
                              option=CloudNlpConfigKeys.USERNAME,
                              default="")
    password = config.get_str(section=CLOUD_NLP_SECTION,
                              option=CloudNlpConfigKeys.PASSWORD,
                              default="")
    filename = f'{req_data_dir}/request_data_{nlpname}.txt'
    available_procs = CloudRequest.list_processors(url,
                                                   username,
                                                   password,
                                                   verify_ssl)
    mirror_procs = nlpdef.get_processors()
    if not os.path.exists(filename):
        log.error(f"File 'request_data_{nlpname}.txt' does not exist in the "
                  f"relevant directory. Request may not have been sent.")
        raise FileNotFoundError
    with open(filename, 'r') as request_data:
        reqdata = request_data.readlines()
    i = 1  # number of requests
    cookies = None
    with open(filename, 'w') as request_data:
        ifconfig_cache = {}  # type: Dict[str, InputFieldConfig]
        all_ready = True  # not necessarily true, but need for later
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
            seen_srchashs = []
            cloud_request = CloudRequest(nlpdef=nlpdef,
                                         url=url,
                                         username=username,
                                         password=password,
                                         allowable_procs=available_procs,
                                         verify_ssl=verify_ssl)
            cloud_request.set_mirror_processors(mirror_procs)
            cloud_request.set_queue_id(queue_id)
            log.info(f"Atempting to retrieve data from request #{i} ...")
            i += 1
            ready = cloud_request.check_if_ready(cookies)
            if cloud_request.cookies:
                cookies = cloud_request.cookies

            if not ready:
                # If results are not ready for this particular queue_id, put
                # back in file
                # For some reason an extra newline is beign appended here
                # but not in 'process_cloud_nlp'
                request_data.write(f"{if_section},{queue_id}\n")
                all_ready = False
            else:
                nlp_data = cloud_request.nlp_data
                for result in nlp_data[NKeys.RESULTS]:
                    # There are records associated with the given queue_id
                    records_exist = True
                    # 'metadata' is just 'other_values' from before
                    metadata = result[NKeys.METADATA]
                    pkval = metadata[FN_SRCPKVAL]
                    pkstr = metadata[FN_SRCPKSTR]
                    srchash = metadata[FN_SRCHASH]
                    progrec = None
                    if incremental:
                        progrec = ifconfig.get_progress_record(pkval, pkstr)
                        if progrec is not None:
                            if progrec.srchash == srchash:
                                log.debug("Record previously processed; "
                                          "skipping")
                                continue
                            else:
                                log.debug("Record has changed")
                        else:
                            log.debug("Record is new")
                        for processor in (
                                cloud_request.mirror_processors.values()):
                            processor.delete_dest_record(ifconfig,
                                                         pkval,
                                                         pkstr,
                                                         commit=incremental)
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
                if records_exist:
                    log.info("Request ready.")
                else:
                    log.warning(f"No records found for queue_id {queue_id}.")
                cloud_request.process_all()
    nlpdef.commit_all()
    if all_ready:
        os.remove(filename)
    else:
        log.info("There are still results to be processed. Re-run this "
                 "command later to retrieve them.")


def process_cloud_now(
        nlpdef: NlpDefinition,
        incremental: bool = False,
        report_every: int = DEFAULT_REPORT_EVERY_NLP,
        verify_ssl: bool = True) -> None:
    """
    Process text by sending it off to the cloud processors in non queued mode.
    """
    session = nlpdef.get_progdb_session()
    mirror_procs = nlpdef.get_processors()
    config = nlpdef.get_parser()
    url = config.get_str(section=CLOUD_NLP_SECTION,
                         option=CloudNlpConfigKeys.URL,
                         required=True)
    username = config.get_str(section=CLOUD_NLP_SECTION,
                              option=CloudNlpConfigKeys.USERNAME,
                              default="")
    password = config.get_str(section=CLOUD_NLP_SECTION,
                              option=CloudNlpConfigKeys.PASSWORD,
                              default="")
    max_length = config.get_int_default_if_failure(
                     section=CLOUD_NLP_SECTION,
                     option=CloudNlpConfigKeys.MAX_LENGTH,
                     default=0)
    for ifconfig in nlpdef.get_ifconfigs():
        seen_srchashs = []
        cloud_requests = send_cloud_requests(
            nlpdef=nlpdef,
            url=url,
            username=username,
            password=password,
            max_length=max_length,
            ifconfig=ifconfig,
            incremental=incremental,
            report_every=report_every,
            queue=False,
            verify_ssl=verify_ssl)
        for cloud_request in cloud_requests:
            cloud_request.set_mirror_processors(mirror_procs)
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
                    for processor in cloud_request.mirror_processors.values():
                        processor.delete_dest_record(ifconfig, pkval, pkstr,
                                                     commit=incremental)
                    # Record progress in progress database
                    progrec = ifconfig.get_progress_record(pkval, pkstr)
                # Check that we haven't already done the progrec for this
                # record to avoid clashes - it's possible as each processor
                # may contain results for each record and a set of results
                # is a list of processors and their results
                if srchash in seen_srchashs:
                    progrec = ifconfig.get_progress_record(pkval, pkstr)
                seen_srchashs.append(srchash)
                # Make a note in the progress database that we've processed a
                # source record
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
            
    nlpdef.commit_all()


def cancel_request(nlpdef: NlpDefinition, cancel_all: bool = False,
                   verify_ssl: bool = True) -> None:
    """
    Delete pending requests from the server's queue.
    """
    nlpname = nlpdef.get_name()
    config = nlpdef.get_parser()
    req_data_dir = config.get_str(section=CLOUD_NLP_SECTION,
                                  option=CloudNlpConfigKeys.REQUEST_DATA_DIR,
                                  required=True)
    url = config.get_str(section=CLOUD_NLP_SECTION,
                         option=CloudNlpConfigKeys.URL,
                         required=True)
    username = config.get_str(section=CLOUD_NLP_SECTION,
                              option=CloudNlpConfigKeys.USERNAME,
                              default="")
    password = config.get_str(section=CLOUD_NLP_SECTION,
                              option=CloudNlpConfigKeys.PASSWORD,
                              default="")
    cloud_request = CloudRequest(nlpdef=nlpdef,
                                 url=url,
                                 username=username,
                                 password=password,
                                 verify_ssl=verify_ssl,
                                 procs_auto_add=False)
    if cancel_all:
        # Deleting all from queue!
        cloud_request.delete_all_from_queue()
        # Shoud the files be deleted in the program or is that dangerous?
        log.info(f"All cloud requests cancelled. Delete files in "
                 "{req_data_dir}")
        return
    filename = f'{req_data_dir}/request_data_{nlpname}.txt'
    if not os.path.exists(filename):
        log.error(f"File 'request_data_{nlpname}.txt' does not exist in the "
                  f"relevant directory. Request may not have been sent.")
        raise FileNotFoundError
    queue_ids = []
    with open(filename, 'r') as request_data:
        reqdata = request_data.readlines()
        for line in reqdata:
            if_section, queue_id = line.strip().split(',')
            queue_ids.append(queue_id)
    cloud_request.delete_from_queue(queue_ids)
    # Remove the file with the request info
    os.remove(filename)
    log.info(f"Cloud request for nlp definition {nlpname} cancelled.")


def show_cloud_queue(nlpdef: NlpDefinition, verify_ssl: bool = True) -> None:
    """
    Get list of the user's queued requests and print to screen.
    """
    config = nlpdef.get_parser()
    url = config.get_str(section=CLOUD_NLP_SECTION,
                         option=CloudNlpConfigKeys.URL,
                         required=True)
    username = config.get_str(section=CLOUD_NLP_SECTION,
                              option=CloudNlpConfigKeys.USERNAME,
                              default="")
    password = config.get_str(section=CLOUD_NLP_SECTION,
                              option=CloudNlpConfigKeys.PASSWORD,
                              default="")
    cloud_request = CloudRequest(nlpdef=nlpdef,
                                 url=url,
                                 username=username,
                                 password=password,
                                 verify_ssl=verify_ssl,
                                 procs_auto_add=False)
    queue = cloud_request.show_queue()
    if not queue:
        print("\nNo requests in queue.")
    for entry in queue:
        print("\nQUEUE ITEM:\n")
        for key in entry:
            print(f"{key}: {entry[key]}")


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
    parser.add_argument(
        "--noverify", action="store_true",
        help="Don't verify server's SSL certificate")
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
        print(DEMO_CONFIG)
        return

    # List or describe processors?
    if args.listprocessors:
        print("\n".join(possible_processor_names()))
        return
    if args.describeprocessors:
        print(possible_processor_table())
        return
    if args.showinfo:
        parser = get_nlp_parser_debug_instance(args.showinfo)
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
    config = NlpDefinition(args.nlpdef,
                           logtag="_".join(mynames).replace(" ", "_"))
    config.set_echo(args.echo)

    # Count only?
    if args.count:
        show_source_counts(config)
        show_dest_counts(config)
        return

    # -------------------------------------------------------------------------

    verify_ssl = not args.noverify

    # Delete from queue - do this before Drop/Remake and return so we don't
    # drop all the tables just to cancel the request
    # Same for 'showqueue'. All of these need config as they require url etc.
    if args.cancelrequest:
        cancel_request(config, verify_ssl=verify_ssl)
        return
    if args.cancelall:
        cancel_request(config, cancel_all=args.cancelall, verify_ssl=verify_ssl)
        return
    if args.showqueue:
        show_cloud_queue(config, verify_ssl=verify_ssl)
        return

    log.info(f"Starting: incremental={args.incremental}")
    start = get_now_utc_pendulum()
    timer.set_timing(args.timing, reset=True)

    # 1. Drop/remake tables. Single-tasking only.
    with MultiTimerContext(timer, TIMING_DROP_REMAKE):
        if args.dropremake or everything:
            drop_remake(config,
                        incremental=args.incremental,
                        skipdelete=args.skipdelete,
                        report_every=args.report_every_fast,
                        chunksize=args.chunksize)

    # From here, in a multiprocessing environment, trap any errors simply so
    # we can report the process number clearly.

    # 2. NLP
    # if args.nlp or everything:
    #     try:
    #         process_nlp(config,
    #                     incremental=args.incremental,
    #                     report_every=args.report_every_nlp,
    #                     tasknum=args.process,
    #                     ntasks=args.nprocesses)
    #     except Exception as exc:
    #         log.critical("TERMINAL ERROR FROM THIS PROCESS")  # so we see proc#  # noqa
    #         die(exc)
    if args.nlp or everything:
        if args.cloud:
            if args.immediate:
                try:
                    process_cloud_now(
                        config,
                        incremental=args.incremental,
                        report_every=args.report_every_nlp,
                        verify_ssl=verify_ssl)
                except Exception as exc:
                    log.critical("TERMINAL ERROR FROM THIS PROCESS")  # so we see proc#  # noqa
                    die(exc)
            else:
                try:
                    process_cloud_nlp(config,
                                      incremental=args.incremental,
                                      report_every=args.report_every_nlp,
                                      verify_ssl=verify_ssl)
                except Exception as exc:
                    log.critical("TERMINAL ERROR FROM THIS PROCESS")  # so we see proc#  # noqa
                    die(exc)
        elif args.retrieve:
            try:
                retrieve_nlp_data(config,
                                  incremental=args.incremental,
                                  verify_ssl=verify_ssl)
            except Exception as exc:
                log.critical("TERMINAL ERROR FROM THIS PROCESS")  # so we see proc#  # noqa
                die(exc)
        else:
            try:
                process_nlp(config,
                            incremental=args.incremental,
                            report_every=args.report_every_nlp,
                            tasknum=args.process,
                            ntasks=args.nprocesses)
            except Exception as exc:
                log.critical("TERMINAL ERROR FROM THIS PROCESS")  # so we see proc#  # noqa
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
