#!/usr/bin/env python
# crate_anon/anonymise/subproc.py

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
"""

import atexit
import logging
from multiprocessing.dummy import Pool  # thread pool
from subprocess import (
    check_call,
    # PIPE,
    Popen,
    # STDOUT,
    TimeoutExpired,
)
import sys
from typing import Any, List

log = logging.getLogger(__name__)

# =============================================================================
# Processes that we're running
# =============================================================================

processes = []
args_list = []  # to report back which process failed, if any did


# =============================================================================
# Exiting
# =============================================================================

@atexit.register
def kill_child_processes() -> None:
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


def fail() -> None:
    print("\nPROCESS FAILED; EXITING ALL\n")
    sys.exit(1)  # will call the atexit handler and kill everything else


# =============================================================================
# Subprocess handling
# =============================================================================

def check_call_process(args: List[str]) -> None:
    log.debug(args)
    check_call(args)


def start_process(args: List[str],
                  stdin: Any = None,
                  stdout: Any = None,
                  stderr: Any = None) -> Popen:
    """

    Args:
        args: program and its arguments, as a list
        stdin: typically None
        stdout: use None to perform no routing, which preserves console colour!
            Otherwise, specify somewhere to route stdout. See subprocess
            documentation. If either is PIPE, you'll need to deal with the
            output.
        stderr: As above. You can use stderr=STDOUT to route stderr to the same
            place as stdout.

    Returns:
        The process object (which is also stored in processes).
    """
    log.debug(args)
    global processes
    global args_list
    proc = Popen(args, stdin=stdin, stdout=stdout, stderr=stderr)
    # proc = Popen(args, stdin=None, stdout=PIPE, stderr=STDOUT)
    # proc = Popen(args, stdin=None, stdout=PIPE, stderr=PIPE)
    # Can't preserve colour: http://stackoverflow.com/questions/13299550/preserve-colored-output-from-python-os-popen  # noqa
    processes.append(proc)
    args_list.append(args)
    return proc


def wait_for_processes(die_on_failure: bool = True,
                       timeout_sec: float = 1) -> None:
    """
    If die_on_failure is True, then whenever a subprocess returns failure,
    all are killed.

    If timeout_sec is None, the function waits for its first process to
    complete, then waits for the second, etc. So a subprocess dying does not
    trigger a full quit instantly (or potentially for ages).

    If timeout_sec is something else, each process is tried for that time;
    if it quits within that time, well and good (successful quit -> continue
    waiting for the others; failure -> kill everything, if die_on_failure);
    if it doesn't, we try the next. That is much more responsive.
    """
    global processes
    global args_list
    Pool(len(processes)).map(print_lines, processes)  # in case of PIPE
    something_running = True
    while something_running:
        something_running = False
        for i, p in enumerate(processes):
            try:
                retcode = p.wait(timeout=timeout_sec)
                if retcode != 0:
                    log.critical(
                        "Process {} exited with return code {} (indicating "
                        "failure); its args were: {}".format(
                            i, retcode, repr(args_list[i])))
                    if die_on_failure:
                        fail()  # exit this process, therefore kill its children  # noqa
            except TimeoutExpired:
                something_running = True
    processes.clear()
    args_list.clear()


def print_lines(process: Popen) -> None:
    out, err = process.communicate()
    if out:
        for line in out.decode("utf-8").splitlines():
            print(line)
    if err:
        for line in err.decode("utf-8").splitlines():
            print(line)


def run_multiple_processes(args_list: List[List[str]],
                           die_on_failure: bool = True) -> None:
    for procargs in args_list:
        start_process(procargs)
    # Wait for them all to finish
    wait_for_processes(die_on_failure=die_on_failure)
