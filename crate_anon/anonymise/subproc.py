#!/usr/bin/env python

import logging
from multiprocessing.dummy import Pool  # thread pool
from subprocess import (
    # check_call,
    # PIPE,
    Popen,
    # STDOUT,
    TimeoutExpired,
)
import sys

log = logging.getLogger(__name__)

processes = []


# =============================================================================
# Subprocess handling
# =============================================================================

def start_process(args):
    log.debug(args)
    global processes
    processes.append(Popen(args))  # preserves colour!
    # processes.append(Popen(args, stdin=None, stdout=PIPE, stderr=STDOUT))
    # processes.append(Popen(args, stdin=None, stdout=PIPE, stderr=PIPE))
    # Can't preserve colour: http://stackoverflow.com/questions/13299550/preserve-colored-output-from-python-os-popen  # noqa


def wait_for_processes():
    global processes
    Pool(len(processes)).map(print_lines, processes)
    for p in processes:
        retcode = p.wait()
        # log.critical("retcode: {}".format(retcode))
        if retcode > 0:
            fail()
    processes.clear()


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
