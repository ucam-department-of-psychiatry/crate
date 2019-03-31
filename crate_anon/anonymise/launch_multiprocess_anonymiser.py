#!/usr/bin/env python

"""
crate_anon/anonymise/launch_multiprocess_anonymiser.py

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

**Launch the CRATE anonymiser in multiprocess mode.**

Previous bash version: see

- http://stackoverflow.com/questions/356100
- http://stackoverflow.com/questions/1644856
- http://stackoverflow.com/questions/8903239
- http://stackoverflow.com/questions/1951506
- Note: ``$!`` is the process ID of last process launched in background
- http://stackoverflow.com/questions/59895

Python version: see

- http://stackoverflow.com/questions/23611396/python-execute-cat-subprocess-in-parallel
- http://stackoverflow.com/questions/320232/ensuring-subprocesses-are-dead-on-exiting-python-program
- http://stackoverflow.com/questions/641420/how-should-i-log-while-using-multiprocessing-in-python
"""  # noqa

import argparse
import logging
import multiprocessing
import sys
import time

from cardinal_pythonlib.logs import configure_logger_for_colour
from cardinal_pythonlib.subproc import (
    check_call_process,
    run_multiple_processes,
)

from crate_anon.version import CRATE_VERSION, CRATE_VERSION_DATE

log = logging.getLogger(__name__)

ANONYMISER = 'crate_anon.anonymise.anonymise_cli'

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
        f"Runs the CRATE anonymiser in parallel. {version}. "
        f"Note that all arguments not specified here are passed to the "
        f"underlying script (see crate_anonymise --help)."
    )
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument(
        "--nproc", "-n", nargs="?", type=int, default=CPUCOUNT,
        help=f"Number of processes (default on this machine: {CPUCOUNT})")
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help="Be verbose")
    args, unknownargs = parser.parse_known_args()

    loglevel = logging.DEBUG if args.verbose else logging.INFO
    rootlogger = logging.getLogger()
    configure_logger_for_colour(rootlogger, level=loglevel)

    common_options = ["-v"] * (1 if args.verbose else 0) + unknownargs

    log.debug(f"common_options: {common_options}")

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
    # Build opt-out lists. Only run one copy of this!
    # -------------------------------------------------------------------------
    procargs = [
        sys.executable, '-m', ANONYMISER,
        '--optout', '--processcluster=OPTOUT',
        '--skip_dd_check'
    ] + common_options
    check_call_process(procargs)

    # -------------------------------------------------------------------------
    # Now run lots of things simultaneously:
    # -------------------------------------------------------------------------
    # It'd be less confusing if we have a single numbering system across all,
    # rather than numbering separately for patient and non-patient processes.
    # However, each group divides its work by its process number, so that
    # won't fly (for n processes it wants to see processes numbered from 0 to
    # n - 1 inclusive).

    # (a) patient tables
    args_list = []
    for procnum in range(nprocesses_patient):
        procargs = [
            sys.executable, '-m', ANONYMISER,
            '--patienttables',
            '--processcluster=PATIENT',
            f'--nprocesses={nprocesses_patient}',
            f'--process={procnum}',
            '--skip_dd_check'
        ] + common_options
        args_list.append(procargs)
    for procnum in range(nprocesses_nonpatient):
        procargs = [
            sys.executable, '-m', ANONYMISER,
            '--nonpatienttables',
            '--processcluster=NONPATIENT',
            f'--nprocesses={nprocesses_nonpatient}',
            f'--process={procnum}',
            '--skip_dd_check'
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
            f'--nprocesses={nprocesses_index}',
            f'--process={procnum}',
            '--skip_dd_check'
        ] + common_options for procnum in range(nprocesses_index)
    ]
    run_multiple_processes(args_list)

    # -------------------------------------------------------------------------
    # Finished.
    # -------------------------------------------------------------------------
    time_end = time.time()
    main_dur = time_middle - time_start
    index_dur = time_end - time_middle
    total_dur = time_end - time_start
    print(f"Time taken: main {main_dur} s, indexing {index_dur} s, "
          f"total {total_dur} s")


if __name__ == '__main__':
    main()
