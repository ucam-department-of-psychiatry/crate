#!/usr/bin/env python

"""
crate_anon/nlp_manager/launch_multiprocess_nlp.py

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

**Launch the NLP processor in multiprocess mode.**

"""

# Previous bash version:
#
# http://stackoverflow.com/questions/356100
# http://stackoverflow.com/questions/1644856
# http://stackoverflow.com/questions/8903239
# http://stackoverflow.com/questions/1951506
# Note: $! is the process ID of last process launched in background
# http://stackoverflow.com/questions/59895
#
# Python version:
#
# http://stackoverflow.com/questions/23611396/python-execute-cat-subprocess-in-parallel  # noqa
# http://stackoverflow.com/questions/320232/ensuring-subprocesses-are-dead-on-exiting-python-program  # noqa
# http://stackoverflow.com/questions/641420/how-should-i-log-while-using-multiprocessing-in-python  # noqa

import argparse
import logging
import multiprocessing
import sys
import time
from typing import List

from cardinal_pythonlib.logs import configure_logger_for_colour
from cardinal_pythonlib.subproc import (
    check_call_process,
    run_multiple_processes,
)

from crate_anon.version import CRATE_VERSION, CRATE_VERSION_DATE

log = logging.getLogger(__name__)

NLP_MANAGER = 'crate_anon.nlp_manager.nlp_manager'

CPUCOUNT = multiprocessing.cpu_count()


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    """
    Command-line processor. See command-line help.
    """
    version = f"Version {CRATE_VERSION} ({CRATE_VERSION_DATE})"
    description = (
        f"Runs the CRATE NLP manager in parallel. {version}. Note that all "
        f"arguments not specified here are passed to the underlying script "
        f"(see crate_nlp --help).")
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument(
        "--nlpdef", required=True,
        help="NLP processing name, from the config file")
    parser.add_argument(
        "--nproc", "-n", nargs="?", type=int, default=CPUCOUNT,
        help=f"Number of processes (default on this machine: {CPUCOUNT})")
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help="Be verbose")
    args, unknownargs = parser.parse_known_args()

    loglevel = logging.DEBUG if args.verbose else logging.INFO
    rootlogger = logging.getLogger()
    configure_logger_for_colour(rootlogger, loglevel)

    common_options = (
        ['--nlpdef', args.nlpdef] +
        ["-v"] * (1 if args.verbose else 0) +
        unknownargs
    )

    log.debug(f"common_options: {common_options}")

    nprocesses_main = args.nproc
    # nprocesses_index = args.nproc

    # -------------------------------------------------------------------------
    # Setup
    # -------------------------------------------------------------------------

    # Start.
    time_start = time.time()

    # -------------------------------------------------------------------------
    # Clean/build the tables. Only run one copy of this!
    # -------------------------------------------------------------------------
    # CALL USING "python -m my.module"; DO NOT run the script as an executable.
    # If you run a Python script as an executable, it gets added to the
    # PYTHONPATH. Then, when your script says "import regex" (meaning the
    # system module), it might import "regex.py" from the same directory (which
    # it wouldn't normally do, because Python 3 uses absolute not relative
    # imports).
    procargs = [
        sys.executable, '-m', NLP_MANAGER,
        '--dropremake',
        '--processcluster', 'STRUCTURE'
    ] + common_options
    check_call_process(procargs)

    # -------------------------------------------------------------------------
    # Now run lots of things simultaneously:
    # -------------------------------------------------------------------------
    # (a) patient tables
    args_list = []  # type: List[List[str]]
    for procnum in range(nprocesses_main):
        procargs = [
            sys.executable, '-m', NLP_MANAGER,
            '--nlp',
            '--processcluster', 'NLP',
            f'--nprocesses={nprocesses_main}',
            f'--process={procnum}'
        ] + common_options
        args_list.append(procargs)
    run_multiple_processes(args_list)  # Wait for them all to finish

    # time_middle = time.time()

    # -------------------------------------------------------------------------
    # We used to index at the end.
    # (Always fastest to index last.)
    # But now we combine index definitions with column definitions in SQLA.
    # -------------------------------------------------------------------------
    # args_list = [
    #     [
    #         sys.executable, '-m', NLP_MANAGER,
    #         '--index',
    #         '--processcluster=INDEX',
    #         f'--nprocesses={nprocesses_index}',
    #         f'--process={procnum}'
    #     ] + common_options for procnum in range(nprocesses_index)
    # ]
    # run_multiple_processes(args_list)  # Wait for them all to finish

    # -------------------------------------------------------------------------
    # Finished.
    # -------------------------------------------------------------------------
    time_end = time.time()

    # main_dur = time_middle - time_start
    # index_dur = time_end - time_middle
    # total_dur = time_end - time_start
    # print(f"Time taken: main {main_dur} s, indexing {index_dur} s, "
    #       f"total {total_dur} s")

    total_dur = time_end - time_start
    print(f"Time taken: {total_dur} s")


if __name__ == '__main__':
    main()
