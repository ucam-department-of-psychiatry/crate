#!/usr/bin/env python
# crate_anon/nlp_manager/nlp_manager.py

"""
===============================================================================
    Copyright (C) 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

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

Manage natural-language processing (NLP) via external tools.

Speed testing:

    - 8 processes, extracting person, location from a mostly text database
    - commit off during full (non-incremental) processing (much faster)
    - needs lots of RAM; e.g. Java subprocess uses 1.4 Gb per process as an
      average (rises from ~250Mb to ~1.4Gb and falls; steady rise means memory
      leak!); tested on a 16 Gb machine. See also the max_external_prog_uses
      parameter.

from __future__ import division
test_size_mb = 1887
n_person_tags_found =
n_locations_tags_found =
time_s = 10333  # 10333 s for main bit; 10465 including indexing; is 2.9 hours
speed_mb_per_s = test_size_mb / time_s

    ... 0.18 Mb/s
    ... and note that's 1.9 Gb of *text*, not of attachments

    - With incremental option, and nothing to do:
        same run took 18 s
    - During the main run, snapshot CPU usage:
        java about 81% across all processes, everything else close to 0
            (using about 12 Gb RAM total)
        ... or 75-85% * 8 [from top]
        mysqld about 18% [from top]
        nlp_manager.py about 4-5% * 8 [from top]

TO DO:
    - comments for NLP output fields (in table definition, destfields)

"""


# =============================================================================
# Imports
# =============================================================================

import argparse
import logging
import os
import sys
from typing import Any, Dict, List, Tuple

from cardinal_pythonlib.rnc_datetime import get_now_utc
from sqlalchemy.schema import Column, Index, Table
from sqlalchemy.types import BigInteger, String
from crate_anon.anonymise.constants import (
    DEFAULT_CHUNKSIZE,
    DEFAULT_REPORT_EVERY,
    TABLE_KWARGS,
    SEP,
)
from crate_anon.common.formatting import print_record_counts
from crate_anon.common.logsupport import configure_logger_for_colour
from crate_anon.common.sqla import count_star
from crate_anon.common.timing import MultiTimerContext, timer
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
from crate_anon.nlp_manager.models import NlpRecord
from crate_anon.nlp_manager.nlp_definition import NlpDefinition
from crate_anon.version import VERSION, VERSION_DATE

log = logging.getLogger(__name__)

TIMING_DROP_REMAKE = "drop_remake"
TIMING_DELETE_WHERE_NO_SOURCE = "delete_where_no_source"
TIMING_PROGRESS_DB_ADD = "progress_db_add"


# =============================================================================
# Database operations
# =============================================================================

def delete_where_no_source(nlpdef: NlpDefinition,
                           ifconfig: InputFieldConfig,
                           report_every: int = DEFAULT_REPORT_EVERY,
                           chunksize: int = DEFAULT_CHUNKSIZE) -> None:
    """
    Delete destination records where source records no longer exist.

    - Can't do this in a single SQL command, since the engine can't necessarily
      see both databases.
    - Can't use a single temporary table, since the progress database isn't
      necessarily the same as any of the destination database(s).
    - Can't do this in a multiprocess way, because we're trying to do a
      DELETE WHERE NOT IN.
    - So we fetch all source PKs (which, by definition, do exist), stash them
      keep them in memory, and do a DELETE WHERE NOT IN based on those
      specified values (or, if there are no PKs in the source, delete
      everything from the destination).

    Problems:
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
    - More efficient would be to make one table per destination database.

    On the "delete where multiple fields don't match":
    - Single field syntax is
        DELETE FROM a WHERE a1 NOT IN (SELECT b1 FROM b)
    - Multiple field syntax is
        DELETE FROM a WHERE NOT EXISTS (
            SELECT 1 FROM b
            WHERE a.a1 = b.b1
            AND a.a2 = b.b2
        )
    - In SQLAlchemy, exists():
        http://stackoverflow.com/questions/14600619
        http://docs.sqlalchemy.org/en/latest/core/selectable.html
    - Furthermore, in SQL NULL = NULL is false, and NULL <> NULL is also false,
      so we have to do an explicit null check.
      You do that with "field == None" (disable
      See http://stackoverflow.com/questions/21668606
      We're aiming, therefore, for:
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
        log.debug("... inserting {} records".format(n_rows))
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

    log.info("delete_where_no_source: examining source table {}.{}; "
             "MAY BE SLOW".format(ifconfig.get_srcdb(),
                                  ifconfig.get_srctable()))

    # Start our list with the progress database
    databases = [{
        'session': nlpdef.get_progdb_session(),
        'engine': nlpdef.get_progdb_engine(),
        'metadata': nlpdef.get_progdb_metadata(),
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
        })

    # Make a temporary table in each database (note: the Table objects become
    # affiliated to their engine, I think, so make separate ones for each).
    log.info("... using {n} destination database(s)".format(n=len(databases)))
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
    log.info("... populating temporary table(s): {} records to go; working in "
             "chunks of {}".format(n, chunksize))
    i = 0
    records = []  # type: List[Dict[str, Any]]
    for pkval, pkstr in ifconfig.gen_src_pks():
        i += 1
        if report_every and i % report_every == 0:
            log.info("... src row# {} / {}".format(i, n))
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


# =============================================================================
# Core functions
# =============================================================================

def process_nlp(nlpdef: NlpDefinition,
                incremental: bool = False,
                report_every: int = DEFAULT_REPORT_EVERY_NLP,
                tasknum: int = 0,
                ntasks: int = 1) -> None:
    """
    Main NLP processing function. Fetch text, send it to the GATE app
    (storing the results), and make a note in the progress database.
    """
    log.info(SEP + "NLP")
    session = nlpdef.get_progdb_session()
    for ifconfig in nlpdef.get_ifconfigs():
        i = 0
        recnum = tasknum
        count = ifconfig.get_count()
        for text, other_values in ifconfig.gen_text(tasknum=tasknum,
                                                    ntasks=ntasks):
            i += 1
            pkval = other_values[FN_SRCPKVAL]
            pkstr = other_values[FN_SRCPKSTR]
            if report_every and i % report_every == 0:
                log.info(
                    "Processing {db}.{t}.{c}, PK: {pkf}={pkv} "
                    "(record {approx}{recnum}/{count})".format(
                        db=other_values[FN_SRCDB],
                        t=other_values[FN_SRCTABLE],
                        c=other_values[FN_SRCFIELD],
                        pkf=other_values[FN_SRCPKFIELD],
                        pkv=pkstr if pkstr else pkval,
                        approx="~" if pkstr and ntasks > 1 else "",
                        # ... string hashing means approx. distribution
                        recnum=recnum + 1,
                        i=i,
                        count=count))
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


def drop_remake(progargs,
                nlpdef: NlpDefinition,
                incremental: bool = False,
                skipdelete: bool = False) -> None:
    """
    Drop output tables and recreate them.
    """
    # Not parallel.
    # -------------------------------------------------------------------------
    # 1. Progress database
    # -------------------------------------------------------------------------
    progengine = nlpdef.get_progdb_engine()
    if not incremental:
        log.debug("Dropping progress tables")
        NlpRecord.__table__.drop(progengine, checkfirst=True)
    log.info("Creating progress table (with index)")
    NlpRecord.__table__.create(progengine, checkfirst=True)

    # -------------------------------------------------------------------------
    # 2. Output database(s)
    # -------------------------------------------------------------------------
    pretty_names = []  # type: List[str]
    for processor in nlpdef.get_processors():
        new_pretty_names = processor.make_tables(drop_first=not incremental)
        for npn in new_pretty_names:
            if npn in pretty_names:
                log.warning("An NLP processor has tried to re-make a table "
                            "made by one of its colleagues: {}".format(npn))
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
                        report_every=progargs.report_every_fast,
                        chunksize=progargs.chunksize)
            else:  # full
                ifconfig.delete_all_progress_records()

    # -------------------------------------------------------------------------
    # 4. Overall commit (superfluous)
    # -------------------------------------------------------------------------
    nlpdef.commit_all()


def show_source_counts(nlpdef: NlpDefinition) -> None:
    """
    Show the number of records in all source tables.
    """
    print("SOURCE TABLE RECORD COUNTS:")
    counts = []  # type: List[Tuple[str, int]]
    for ifconfig in nlpdef.get_ifconfigs():
        session = ifconfig.get_source_session()
        dbname = ifconfig.get_srcdb()
        tablename = ifconfig.get_srctable()
        n = count_star(session, tablename)
        counts.append(("{}.{}".format(dbname, tablename), n))
    print_record_counts(counts)


def show_dest_counts(nlpdef: NlpDefinition) -> None:
    """
    Show the number of records in all destination tables.
    """
    print("DESTINATION TABLE RECORD COUNTS:")
    counts = []  # type: List[Tuple[str, int]]
    for processor in nlpdef.get_processors():
        session = processor.get_session()
        dbname = processor.get_dbname()
        for tablename in processor.get_tablenames():
            n = count_star(session, tablename)
            counts.append(("DESTINATION: {}.{}".format(dbname, tablename), n))
    print_record_counts(counts)


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    """
    Command-line entry point.
    """
    version = "Version {} ({})".format(VERSION, VERSION_DATE)
    description = "NLP manager. {version}. By Rudolf Cardinal.".format(
        version=version)

    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=version)
    parser.add_argument("--config",
                        help="Config file (overriding environment "
                             "variable {})".format(NLP_CONFIG_ENV_VAR))
    parser.add_argument('--verbose', '-v', action='store_true',
                        help="Be verbose (use twice for extra verbosity)")
    parser.add_argument("--nlpdef", nargs="?", default=None,
                        help="NLP definition name (from config file)")
    parser.add_argument('--report_every_fast', nargs="?", type=int,
                        default=DEFAULT_REPORT_EVERY,
                        help="Report insert progress (for fast operations) "
                             "every n rows in verbose "
                             "mode (default {})".format(DEFAULT_REPORT_EVERY))
    parser.add_argument('--report_every_nlp', nargs="?", type=int,
                        default=DEFAULT_REPORT_EVERY_NLP,
                        help="Report progress for NLP every n rows in verbose "
                             "mode (default "
                             "{})".format(DEFAULT_REPORT_EVERY_NLP))
    parser.add_argument('--chunksize', nargs="?", type=int,
                        default=DEFAULT_CHUNKSIZE,
                        help="Number of records copied in a chunk when copying"
                             " PKs from one database to another"
                             " (default {})".format(DEFAULT_CHUNKSIZE))
    parser.add_argument("--process", nargs="?", type=int, default=0,
                        help="For multiprocess mode: specify process number")
    parser.add_argument("--nprocesses", nargs="?", type=int, default=1,
                        help="For multiprocess mode: specify "
                             "total number of processes (launched somehow, of "
                             "which this is to be one)")
    parser.add_argument("--processcluster", default="",
                        help="Process cluster name")
    parser.add_argument("--democonfig", action="store_true",
                        help="Print a demo config file")
    parser.add_argument("--listprocessors", action="store_true",
                        help="Show possible built-in NLP processor names")
    parser.add_argument("--describeprocessors", action="store_true",
                        help="Show details of built-in NLP processors")
    parser.add_argument("--showinfo", required=False, nargs='?',
                        metavar="NLP_CLASS_NAME",
                        help="Show detailed information for a parser")
    parser.add_argument("--count", action="store_true",
                        help="Count records in source/destination databases, "
                             "then stop")

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("-i", "--incremental", dest="incremental",
                            action="store_true",
                            help="Process only new/changed information, where "
                                 "possible (* default)")
    mode_group.add_argument("-f", "--full", dest="incremental",
                            action="store_false",
                            help="Drop and remake everything")
    parser.set_defaults(incremental=True)

    parser.add_argument("--dropremake", action="store_true",
                        help="Drop/remake destination tables only")
    parser.add_argument("--skipdelete", dest="skipdelete", action="store_true",
                        help="For incremental updates, skip deletion of rows "
                             "present in the destination but not the source")
    parser.add_argument("--nlp", action="store_true",
                        help="Perform NLP processing only")
    parser.add_argument("--echo", action="store_true",
                        help="Echo SQL")
    parser.add_argument("--timing", action="store_true",
                        help="Show detailed timing breakdown")
    args = parser.parse_args()

    # Validate args
    if args.nprocesses < 1:
        raise ValueError("--nprocesses must be >=1")
    if args.process < 0 or args.process >= args.nprocesses:
        raise ValueError(
            "--process argument must be from 0 to (nprocesses - 1) inclusive")
    if args.config:
        os.environ[NLP_CONFIG_ENV_VAR] = args.config

    # Verbosity and logging
    mynames = []  # type: List[str]
    if args.processcluster:
        mynames.append(args.processcluster)
    if args.nprocesses > 1:
        mynames.append("proc{}".format(args.process))
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
            print("Info for class {}:\n".format(args.showinfo))
            parser.print_info()
        else:
            print("No such processor class: {}".format(args.showinfo))
        return

    # Otherwise, we need a valid NLP definition.
    if args.nlpdef is None:
        raise ValueError(
            "Must specify nlpdef parameter (unless --democonfig, "
            "--listprocessors, or --describeprocessors used)")

    everything = not any([args.dropremake, args.nlp])

    # Report args
    log.debug("arguments: {}".format(args))

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

    log.info("Starting: incremental={}".format(args.incremental))
    start = get_now_utc()
    timer.set_timing(args.timing, reset=True)

    # 1. Drop/remake tables. Single-tasking only.
    with MultiTimerContext(timer, TIMING_DROP_REMAKE):
        if args.dropremake or everything:
            drop_remake(args, config, incremental=args.incremental,
                        skipdelete=args.skipdelete)

    # From here, in a multiprocessing environment, trap any errors simply so
    # we can report the process number clearly.

    # 2. NLP
    if args.nlp or everything:
        try:
            process_nlp(config,
                        incremental=args.incremental,
                        report_every=args.report_every_nlp,
                        tasknum=args.process,
                        ntasks=args.nprocesses)
        except:
            log.critical("TERMINAL ERROR FROM THIS PROCESS")  # so we see proc#
            raise

    log.info("Finished")
    end = get_now_utc()
    time_taken = end - start
    log.info("Time taken: {:.3f} seconds".format(time_taken.total_seconds()))

    if args.timing:
        timer.report()


# =============================================================================
# Command-line entry point
# =============================================================================

if __name__ == '__main__':
    main()
