#!/usr/bin/env python

"""
crate_anon/anonymise/launch_multiprocess_anonymiser.py

===============================================================================

    Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

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
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

===============================================================================

**Launch the CRATE anonymiser in multiprocess mode.**

Previous bash version: see

- https://stackoverflow.com/questions/356100
- https://stackoverflow.com/questions/1644856
- https://stackoverflow.com/questions/8903239
- https://stackoverflow.com/questions/1951506
- Note: ``$!`` is the process ID of last process launched in background
- https://stackoverflow.com/questions/59895

Python version: see

- https://stackoverflow.com/questions/23611396/python-execute-cat-subprocess-in-parallel
- https://stackoverflow.com/questions/320232/ensuring-subprocesses-are-dead-on-exiting-python-program
- https://stackoverflow.com/questions/641420/how-should-i-log-while-using-multiprocessing-in-python
"""  # noqa: E501

import argparse
import logging
import multiprocessing
import os
import sys
import time
from typing import List

from cardinal_pythonlib.logs import configure_logger_for_colour
from cardinal_pythonlib.subproc import (
    check_call_process,
    run_multiple_processes,
)
from rich_argparse import ArgumentDefaultsRichHelpFormatter

from crate_anon.common.constants import EnvVar
from crate_anon.version import CRATE_VERSION, CRATE_VERSION_DATE

log = logging.getLogger(__name__)

ANONYMISER = "crate_anon.anonymise.anonymise_cli"

if EnvVar.GENERATING_CRATE_DOCS in os.environ:
    CPUCOUNT = 8
else:
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
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=ArgumentDefaultsRichHelpFormatter,
    )

    parser.add_argument(
        "--nproc",
        "-n",
        nargs="?",
        type=int,
        default=CPUCOUNT,
        help="Number of processes "
        "(default is the number of CPUs on this machine)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Be verbose"
    )
    args, unknownargs = parser.parse_known_args()

    loglevel = logging.DEBUG if args.verbose else logging.INFO
    rootlogger = logging.getLogger()
    configure_logger_for_colour(rootlogger, level=loglevel)

    common_launcher = [sys.executable, "-m", ANONYMISER]
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
    procargs = (
        common_launcher
        + ["--dropremake", "--processcluster=STRUCTURE"]
        + common_options
    )
    check_call_process(procargs)

    # -------------------------------------------------------------------------
    # Build opt-out lists. Only run one copy of this!
    # -------------------------------------------------------------------------
    procargs = (
        common_launcher
        + ["--optout", "--processcluster=OPTOUT", "--skip_dd_check"]
        + common_options
    )
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
    args_list = []  # type: List[List[str]]
    for procnum in range(nprocesses_patient):
        procargs = (
            common_launcher
            + [
                "--patienttables",
                "--processcluster=PATIENT",
                f"--nprocesses={nprocesses_patient}",
                f"--process={procnum}",
                "--skip_dd_check",
            ]
            + common_options
        )
        args_list.append(procargs)
    # (b) non-patient tables
    for procnum in range(nprocesses_nonpatient):
        procargs = (
            common_launcher
            + [
                "--nonpatienttables",
                "--processcluster=NONPATIENT",
                f"--nprocesses={nprocesses_nonpatient}",
                f"--process={procnum}",
                "--skip_dd_check",
            ]
            + common_options
        )
        args_list.append(procargs)
    run_multiple_processes(args_list)  # Wait for them all to finish
    # todo: fix cardinal_pythonlib to allow requesting e.g. n processes in
    # total but only n/2 at once

    time_middle = time.time()

    # -------------------------------------------------------------------------
    # Now do the indexing, if nothing else failed.
    # (Always fastest to index last.)
    # -------------------------------------------------------------------------
    args_list = [
        common_launcher
        + [
            "--index",
            "--processcluster=INDEX",
            f"--nprocesses={nprocesses_index}",
            f"--process={procnum}",
            "--skip_dd_check",
        ]
        + common_options
        for procnum in range(nprocesses_index)
    ]
    run_multiple_processes(args_list)

    # -------------------------------------------------------------------------
    # Finished.
    # -------------------------------------------------------------------------
    time_end = time.time()
    main_dur = time_middle - time_start
    index_dur = time_end - time_middle
    total_dur = time_end - time_start
    print(
        f"Time taken: main {main_dur} s, indexing {index_dur} s, "
        f"total {total_dur} s"
    )


if __name__ == "__main__":
    main()
