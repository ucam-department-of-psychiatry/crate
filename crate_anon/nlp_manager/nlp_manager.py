#!/usr/bin/env python
# crate_anon/nlp_manager/nlp_manager.py

"""
Manage natural-language processing (NLP) via external tools.

Author: Rudolf Cardinal
Created at: 26 Feb 2015
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

from cardinal_pythonlib.rnc_datetime import get_now_utc

from crate_anon.anonymise.constants import SEP
from crate_anon.common.logsupport import configure_logger_for_colour
from crate_anon.nlp_manager.all_processors import possible_processor_table
from crate_anon.nlp_manager.constants import (
    DEMO_CONFIG,
    NLP_CONFIG_ENV_VAR,
)
from crate_anon.nlp_manager.input_field_config import (
    InputFieldConfig,
    FN_SRCDB,
    FN_SRCTABLE,
    FN_SRCPKFIELD,
    FN_SRCPKVAL,
    FN_SRCFIELD,
)
from crate_anon.nlp_manager.models import NlpRecord
from crate_anon.nlp_manager.nlp_definition import NlpDefinition
from crate_anon.version import VERSION, VERSION_DATE

log = logging.getLogger(__name__)


# =============================================================================
# Database operations
# =============================================================================

def insert_into_progress_db(config: NlpDefinition,
                            ifconfig: InputFieldConfig,
                            srcpkval: int,
                            srchash: str,
                            commit: bool = False) -> None:
    """
    Make a note in the progress database that we've processed a source record.
    """
    session = config.get_progdb_session()
    progrec = ifconfig.get_progress_record(srcpkval, srchash=None)
    if progrec is None:
        progrec = NlpRecord(
            srcdb=ifconfig.get_srcdb(),
            srctable=ifconfig.get_srctable(),
            srcpkfield=ifconfig.get_srcpkfield(),
            srcpkval=srcpkval,
            srcfield=ifconfig.get_srcfield(),
            nlpdef=config.get_name(),
            whenprocessedutc=config.get_now(),
            srchash=srchash,
        )
        session.add(progrec)
    else:
        progrec.whenprocessedutc = config.get_now()
        progrec.srchash = srchash
    if commit:
        session.commit()
    # Commit immediately, because other processes may need this table promptly.


def delete_where_no_source(config: NlpDefinition,
                           ifconfig: InputFieldConfig) -> None:
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
    """

    src_pks = list(ifconfig.gen_src_pks())
    log.debug("delete_where_no_source: from {}.{}".format(
        ifconfig.get_srcdb(), ifconfig.get_srctable()))

    # 1. Progress database
    ifconfig.delete_progress_records_where_srcpk_not(src_pks)

    # 2. Others. Combine in the same function as we re-use the source PKs.
    for processor in config.get_processors():
        processor.delete_where_srcpk_not(ifconfig, src_pks)


# =============================================================================
# Core functions
# =============================================================================

def process_nlp(config: NlpDefinition,
                incremental: bool = False,
                tasknum: int = 0,
                ntasks: int = 1) -> None:
    """
    Main NLP processing function. Fetch text, send it to the GATE app
    (storing the results), and make a note in the progress database.
    """
    log.info(SEP + "NLP")
    for ifconfig in config.get_ifconfigs():
        count, maximum = ifconfig.get_count_max()
        for text, other_values in ifconfig.gen_text(tasknum=tasknum,
                                                    ntasks=ntasks):
            pkval = other_values[FN_SRCPKVAL]
            log.info(
                "Processing {db}.{t}.{c}, {pkf}={pkv} "
                "(max={maximum}, n={count})".format(
                    db=other_values[FN_SRCDB],
                    t=other_values[FN_SRCTABLE],
                    c=other_values[FN_SRCFIELD],
                    pkf=other_values[FN_SRCPKFIELD],
                    pkv=pkval,
                    maximum=maximum,
                    count=count))
            srchash = config.hash(text)
            if incremental:
                if ifconfig.get_progress_record(pkval, srchash) is not None:
                    log.debug("Record previously processed; skipping")
                    continue
            for processor in config.get_processors():
                if incremental:
                    processor.delete_dest_record(ifconfig, pkval,
                                                 commit=incremental)
                processor.process(text, other_values)
            insert_into_progress_db(config, ifconfig, pkval, srchash,
                                    commit=incremental)
    config.commit_all()


def drop_remake(config: NlpDefinition,
                incremental: bool = False) -> None:
    """
    Drop output tables and recreate them.
    """
    # Not parallel.
    # -------------------------------------------------------------------------
    # 1. Progress database
    # -------------------------------------------------------------------------
    progengine = config.get_progdb_engine()
    if not incremental:
        log.debug("Dropping progress tables")
        NlpRecord.__table__.drop(progengine, checkfirst=True)
    log.info("Creating progress table (with index)")
    NlpRecord.__table__.create(progengine, checkfirst=True)

    # -------------------------------------------------------------------------
    # 2. Output database(s)
    # -------------------------------------------------------------------------
    for processor in config.get_processors():
        processor.make_tables(drop_first=not incremental)

    # -------------------------------------------------------------------------
    # 3. Delete WHERE NOT IN for incremental
    # -------------------------------------------------------------------------
    if incremental:
        for ifconfig in config.get_ifconfigs():
            delete_where_no_source(config, ifconfig)

    # -------------------------------------------------------------------------
    # 4. Overall commit (superfluous)
    # -------------------------------------------------------------------------
    config.commit_all()


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
    parser.add_argument("-n", "--version", action="version", version=version)
    parser.add_argument("--config",
                        help="Config file (overriding environment "
                             "variable {})".format(NLP_CONFIG_ENV_VAR))
    parser.add_argument('--verbose', '-v', action='count', default=0,
                        help="Be verbose (use twice for extra verbosity)")
    parser.add_argument("--nlpdef", nargs="?", default=None,
                        help="NLP definition name (from config file)")
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
                        help="Print a demo config file")
    parser.add_argument("--listprocessors", action="store_true",
                        help="Show possible NLP processor names")

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "-i", "--incremental", dest="incremental", action="store_true",
        help="Process only new/changed information, where possible "
             "(* default)")
    mode_group.add_argument(
        "-f", "--full", dest="incremental", action="store_false",
        help="Drop and remake everything")
    parser.set_defaults(incremental=True)

    parser.add_argument("--dropremake", action="store_true",
                        help="Drop/remake destination tables only")
    parser.add_argument("--nlp", action="store_true",
                        help="Perform NLP processing only")
    parser.add_argument("--echo", action="store_true",
                        help="Echo SQL")
    args = parser.parse_args()

    # Demo config?
    if args.democonfig:
        print(DEMO_CONFIG)
        return
    # List processors?
    if args.listprocessors:
        print(possible_processor_table())
        return
    if args.nlpdef is None:
        raise ValueError(
            "Must specify nlpdef parameter (unless --democonfig used)")
    if args.config:
        os.environ[NLP_CONFIG_ENV_VAR] = args.config

    # Validate args
    if args.nprocesses < 1:
        raise ValueError("--nprocesses must be >=1")
    if args.process < 0 or args.process >= args.nprocesses:
        raise ValueError(
            "--process argument must be from 0 to (nprocesses - 1) inclusive")

    everything = not any([args.dropremake, args.nlp])

    # -------------------------------------------------------------------------

    # Verbosity
    mynames = []
    if args.processcluster:
        mynames.append(args.processcluster)
    if args.nprocesses > 1:
        mynames.append("proc{}".format(args.process))
    loglevel = logging.DEBUG if args.verbose >= 1 else logging.INFO
    rootlogger = logging.getLogger()
    configure_logger_for_colour(rootlogger, level=loglevel, extranames=mynames)

    # Report args
    log.debug("arguments: {}".format(args))

    # Load/validate config
    config = NlpDefinition(args.nlpdef,
                           logtag="_".join(mynames).replace(" ", "_"))
    config.set_echo(args.echo)

    # -------------------------------------------------------------------------

    log.info("Starting")
    start = get_now_utc()

    # 1. Drop/remake tables. Single-tasking only.
    if args.dropremake or everything:
        drop_remake(config, incremental=args.incremental)

    # 2. NLP
    if args.nlp or everything:
        process_nlp(config,
                    incremental=args.incremental,
                    tasknum=args.process, ntasks=args.nprocesses)

    log.info("Finished")
    end = get_now_utc()
    time_taken = end - start
    log.info("Time taken: {} seconds".format(time_taken.total_seconds()))


# =============================================================================
# Command-line entry point
# =============================================================================

if __name__ == '__main__':
    main()

# *** deal with two processors trying to make the same table
