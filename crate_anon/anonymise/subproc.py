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
    print()
    print("PROCESS FAILED; EXITING ALL")
    print()
    sys.exit(1)  # will call the atexit handler and kill everything else


# =============================================================================
# Subprocess handling
# =============================================================================

def check_call_process(args):
    log.debug(args)
    check_call(args)


def start_process(args):
    log.debug(args)
    global processes
    processes.append(Popen(args))  # preserves colour!
    # processes.append(Popen(args, stdin=None, stdout=PIPE, stderr=STDOUT))
    # processes.append(Popen(args, stdin=None, stdout=PIPE, stderr=PIPE))
    # Can't preserve colour: http://stackoverflow.com/questions/13299550/preserve-colored-output-from-python-os-popen  # noqa


def wait_for_processes(die_on_failure=True):
    global processes
    if die_on_failure:
        atexit.register(kill_child_processes)
    Pool(len(processes)).map(print_lines, processes)
    for p in processes:
        retcode = p.wait()
        # log.critical("retcode: {}".format(retcode))
        if die_on_failure and retcode > 0:
            fail()
    processes.clear()
    if die_on_failure:
        atexit.register(kill_child_processes)


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
