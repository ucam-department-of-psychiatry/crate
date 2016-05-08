#!/usr/bin/env python
# crate_anon/anonymise/launch_multiprocess_anonymiser.py

"""
Launch anonymise.py in multiprocess mode.

Author: Rudolf Cardinal
Copyright (C) 2015-2016 Rudolf Cardinal.
License: http://www.apache.org/licenses/LICENSE-2.0

Previous bash version:

http://stackoverflow.com/questions/356100
http://stackoverflow.com/questions/1644856
http://stackoverflow.com/questions/8903239
http://stackoverflow.com/questions/1951506
Note: $! is the process ID of last process launched in background
http://stackoverflow.com/questions/59895

Python version:

http://stackoverflow.com/questions/23611396/python-execute-cat-subprocess-in-parallel  # noqa
http://stackoverflow.com/questions/320232/ensuring-subprocesses-are-dead-on-exiting-python-program  # noqa
http://stackoverflow.com/questions/641420/how-should-i-log-while-using-multiprocessing-in-python  # noqa
"""

import argparse
import logging
import multiprocessing
import sys
import time

from crate_anon.anonymise.logsupport import configure_logger_for_colour
from crate_anon.anonymise.subproc import (
    check_call_process,
    run_multiple_processes,
)
from crate_anon.version import VERSION, VERSION_DATE

log = logging.getLogger(__name__)

ANONYMISER = 'crate_anon.anonymise.anonymise_main'

CPUCOUNT = multiprocessing.cpu_count()


# =============================================================================
# Main
# =============================================================================

def main():
    version = "Version {} ({})".format(VERSION, VERSION_DATE)
    description = "Runs the CRATE anonymiser in parallel. {}.".format(version)
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument(
        'mode', choices=('incremental', 'full'),
        help="Processing mode (full or incremental)")
    parser.add_argument(
        "--nproc", "-n", nargs="?", type=int, default=CPUCOUNT,
        help="Number of processes (default: {})".format(CPUCOUNT))
    parser.add_argument(
        '--verbose', '-v', action='count', default=0,
        help="Be verbose (use twice for extra verbosity)")
    parser.add_argument("--echo", action="store_true",
                        help="Echo SQL")
    args = parser.parse_args()

    loglevel = logging.DEBUG if args.verbose > 0 else logging.INFO
    rootlogger = logging.getLogger()
    configure_logger_for_colour(rootlogger, level=loglevel)

    common_options = ["-v"] * args.verbose
    if args.echo:
        common_options.append('--echo')
    if args.mode == 'incremental':
        common_options.append('--incremental')
    else:
        common_options.append('--full')

    log.debug("common_options: {}".format(common_options))

    nprocesses_patient = args.nproc
    nprocesses_nonpatient = args.nproc
    nprocesses_index = args.nproc

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
        sys.executable, '-m', ANONYMISER,
        '--dropremake', '--processcluster=STRUCTURE'
    ] + common_options
    check_call_process(procargs)

    # -------------------------------------------------------------------------
    # Now run lots of things simultaneously:
    # -------------------------------------------------------------------------
    # (a) patient tables
    args_list = []
    for procnum in range(nprocesses_patient):
        procargs = [
            sys.executable, '-m', ANONYMISER,
            '--patienttables',
            '--processcluster=PATIENT',
            '--nprocesses={}'.format(nprocesses_patient),
            '--process={}'.format(procnum)
        ] + common_options
        args_list.append(procargs)
    for procnum in range(nprocesses_nonpatient):
        procargs = [
            sys.executable, '-m', ANONYMISER,
            '--nonpatienttables',
            '--processcluster=NONPATIENT',
            '--nprocesses={}'.format(nprocesses_nonpatient),
            '--process={}'.format(procnum)
        ] + common_options
        args_list.append(procargs)
    run_multiple_processes(args_list)  # Wait for them all to finish

    time_middle = time.time()

    # -------------------------------------------------------------------------
    # Now do the indexing, if nothing else failed.
    # (Always fastest to index last.)
    # -------------------------------------------------------------------------
    args_list = [
        [
            sys.executable, '-m', ANONYMISER,
            '--index',
            '--processcluster=INDEX',
            '--nprocesses={}'.format(nprocesses_index),
            '--process={}'.format(procnum)
        ] for procnum in range(nprocesses_index)
    ]
    run_multiple_processes(args_list)

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
