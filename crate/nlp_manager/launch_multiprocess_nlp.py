#!/usr/bin/env python
#
# Launch nlp_manager.py in multiprocess mode.
#
# Author: Rudolf Cardinal
# Copyright (C) 2015-2015 Rudolf Cardinal.
# License: http://www.apache.org/licenses/LICENSE-2.0
#
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
import atexit
import logging
log = logging.getLogger(__name__)
import multiprocessing
from multiprocessing.dummy import Pool  # thread pool
from subprocess import (
    check_call,
    PIPE,
    Popen,
    STDOUT,
    TimeoutExpired,
)
import sys
import time

from crate.version import VERSION, VERSION_DATE

NLP_MANAGER = 'crate.nlp_manager.nlp_manager'

CPUCOUNT = multiprocessing.cpu_count()

DEFAULT_NLP_NAME = 'name_location_nlp'

processes = []


# =============================================================================
# Subprocess handling
# =============================================================================

def start_process(args):
    log.debug(args)
    global processes
    processes.append(Popen(args, stdin=None, stdout=PIPE, stderr=STDOUT))


def wait_for_processes():
    global processes
    Pool(len(processes)).map(print_lines, processes)
    for p in processes:
        retcode = p.wait()
        # log.critical("retcode: {}".format(retcode))
        if retcode > 0:
            fail()
    processes = []


def print_lines(process):
    out, err = process.communicate()
    if out:
        for line in out.decode("utf-8").splitlines():
            print(line)
    if err:
        for line in err.decode("utf-8").splitlines():
            print(line)


def kill_child_processes():
    timeout_sec = 5
    for p in processes:
        try:
            p.wait(timeout_sec)
        except TimeoutExpired:
            p.terminate()  # please stop
            try:
                p.wait(timeout=timeout_sec)
            except TimeoutExpired:
                # failed to close
                p.kill()  # you're dead


def fail():
    print()
    print("PROCESS FAILED; EXITING ALL")
    print()
    sys.exit(1)  # will call the atexit handler and kill everything else


# =============================================================================
# Main
# =============================================================================

def main():
    version = "Version {} ({})".format(VERSION, VERSION_DATE)
    description = "Runs the CRATE NLP manager in parallel. {}.".format(version)
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument(
        'mode', choices=('incremental', 'full'),
        help="Processing mode (full or incremental)")
    parser.add_argument('config', help="Config file")
    parser.add_argument(
        "--nlpname", "-a", default=DEFAULT_NLP_NAME,
        help="NLP processing name, from the config file (default: {})".format(
            DEFAULT_NLP_NAME)
    )
    parser.add_argument(
        "--nproc", "-n", nargs="?", type=int, default=CPUCOUNT,
        help="Number of processes (default: {})".format(CPUCOUNT))
    parser.add_argument(
        '--verbose', '-v', action='count', default=0,
        help="Be verbose (use twice for extra verbosity)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose > 0
                        else logging.INFO)

    common_options = ["-v"] * args.verbose
    if args.mode == 'incremental':
        common_options.append('--incremental')

    log.debug("common_options: {}".format(common_options))

    nprocesses_main = args.nproc
    nprocesses_index = args.nproc

    # -------------------------------------------------------------------------
    # Setup
    # -------------------------------------------------------------------------

    # Kill all subprocesses if this script is aborted
    atexit.register(kill_child_processes)

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
        args.config, args.nlpname,
        '--dropremake', '--processcluster=STRUCTURE'
    ] + common_options
    log.debug(procargs)
    check_call(procargs)

    # -------------------------------------------------------------------------
    # Now run lots of things simultaneously:
    # -------------------------------------------------------------------------
    # (a) patient tables
    global processes
    processes = []
    for procnum in range(nprocesses_main):
        procargs = [
            sys.executable, '-m', NLP_MANAGER,
            args.config, args.nlpname,
            '--nlp',
            '--processcluster=NLP',
            '--nprocesses={}'.format(nprocesses_main),
            '--process={}'.format(procnum)
        ] + common_options
        start_process(procargs)

    # Wait for them all to finish
    wait_for_processes()

    time_middle = time.time()

    # -------------------------------------------------------------------------
    # Now do the indexing, if nothing else failed.
    # (Always fastest to index last.)
    # -------------------------------------------------------------------------
    processes = [
        Popen([
            sys.executable, '-m', NLP_MANAGER,
            args.config, args.nlpname,
            '--index',
            '--processcluster=INDEX',
            '--nprocesses={}'.format(nprocesses_index),
            '--process={}'.format(procnum)
        ] + common_options) for procnum in range(nprocesses_index)
    ]

    wait_for_processes()

    # -------------------------------------------------------------------------
    # Finished.
    # -------------------------------------------------------------------------
    time_end = time.time()
    main_dur = time_middle - time_start
    index_dur = time_end - time_middle
    total_dur = time_end - time_start
    print("Time taken: main {} s, indexing {} s, total {} s".format(
        main_dur, index_dur, total_dur))


if __name__ == '__main__':
    main()
