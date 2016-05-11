#!/usr/bin/env python

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

log = logging.getLogger(__name__)

# =============================================================================
# Processes that we're running
# =============================================================================

processes = []


# =============================================================================
# Exiting
# =============================================================================

@atexit.register
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
    print("\nPROCESS FAILED; EXITING ALL\n")
    sys.exit(1)  # will call the atexit handler and kill everything else


# =============================================================================
# Subprocess handling
# =============================================================================

def check_call_process(args):
    log.debug(args)
    check_call(args)


def start_process(args, stdin=None, stdout=None, stderr=None):
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
    proc = Popen(args, stdin=stdin, stdout=stdout, stderr=stderr)
    # proc = Popen(args, stdin=None, stdout=PIPE, stderr=STDOUT)
    # proc = Popen(args, stdin=None, stdout=PIPE, stderr=PIPE)
    # Can't preserve colour: http://stackoverflow.com/questions/13299550/preserve-colored-output-from-python-os-popen  # noqa
    processes.append(proc)
    return proc


def wait_for_processes(die_on_failure=True, timeout_sec=1):
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
    Pool(len(processes)).map(print_lines, processes)  # in case of PIPE
    something_running = True
    while something_running:
        something_running = False
        for p in processes:
            try:
                retcode = p.wait(timeout=timeout_sec)
                # log.critical("retcode: {}".format(retcode))
                if die_on_failure and retcode > 0:
                    fail()  # exit this process, therefore kill its children
            except TimeoutExpired:
                something_running = True
    processes.clear()


def print_lines(process):
    out, err = process.communicate()
    if out:
        for line in out.decode("utf-8").splitlines():
            print(line)
    if err:
        for line in err.decode("utf-8").splitlines():
            print(line)


def run_multiple_processes(args_list, die_on_failure=True):
    for procargs in args_list:
        start_process(procargs)
    # Wait for them all to finish
    wait_for_processes(die_on_failure=die_on_failure)
