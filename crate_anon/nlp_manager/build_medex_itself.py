#!/usr/bin/env python
# crate_anon/nlp_manager/build_medex_itself.py

"""
Script to compile Java source for MedEx-UIMA.

Author: Rudolf Cardinal
Copyright (C) 2015-2016 Rudolf Cardinal.
License: http://www.apache.org/licenses/LICENSE-2.0
"""

import argparse
import logging
import os
import subprocess
import sys

from crate_anon.common.fileops import purge
from crate_anon.common.logsupport import configure_logger_for_colour


log = logging.getLogger(__name__)

DEFAULT_MEDEX_DIR = os.path.join(os.path.expanduser('~'), 'dev',
                                 'Medex_UIMA_1.3.6')
DEFAULT_JAVA = 'java'
DEFAULT_JAVAC = 'javac'

EXTRA_ROUTES = [
    "i/m",
    "i.m.",
    "i. m.",
    "intramuscularly",
    "intramuscular inj.",
    "intramuscular injection",
    "inh",
    "inh.",
    "i/v",
    "i.v.",
    "i. v.",
    "nasal",
    "nasally",
    "nebs",
    "nebulised",
    "nebuliser",
    "nebulized",
    "nebulizer",
    "ng",
    "n/g",
    "n.g.",
    "n. g.",
    "nasogastric",
    "nasogastrically",
    "nj",
    "n/j",
    "n.j.",
    "n. j.",
    "p/o",
    "p.o.",
    "p. o.",
    "pr",
    "p/r",
    "p.r.",
    "p. r.",
    "s/c",
    "s.c.",
    "s. c.",
    "top",
    "top.",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compile MedEx-UIMA itself (in Java)")
    parser.add_argument(
        '--medexdir', default=DEFAULT_MEDEX_DIR,
        help="Root directory of MedEx installation (default: {})".format(
            DEFAULT_MEDEX_DIR))
    parser.add_argument(
        '--java', default=DEFAULT_JAVA,
        help="Java executable (default: {})".format(DEFAULT_JAVA))
    parser.add_argument(
        '--javac', default=DEFAULT_JAVAC,
        help="Java compiler (default: {})".format(DEFAULT_JAVAC))
    parser.add_argument(
        '--deletefirst', action='store_true',
        help="Delete existing .class files first (optional)")
    parser.add_argument(
        '--extraroutes', action='store_true',
        help="Don't compile; print extra routes of administration to append "
             "to MedEx's lexicon.cfg")
    parser.add_argument('--verbose', '-v', action='count', default=0,
                        help="Be verbose")
    args = parser.parse_args()

    loglevel = logging.DEBUG if args.verbose >= 1 else logging.INFO
    rootlogger = logging.getLogger()
    configure_logger_for_colour(rootlogger, level=loglevel)
    
    if args.extraroutes:
        for route in EXTRA_ROUTES:
            print("{}\tRUT".format(route))
        sys.exit(0)

    bindir = os.path.join(args.medexdir, 'bin')
    classpath = os.pathsep.join([
        os.path.join(args.medexdir, 'src'),
        os.path.join(args.medexdir, 'lib', '*'),  # jar files
    ])
    classpath_options = ['-classpath', classpath]

    os.chdir(args.medexdir)
    if args.deletefirst:
        purge(args.medexdir, '*.class')
    cmdargs = (
        [args.javac] +
        classpath_options +
        ['src/org/apache/medex/Main.java'] +
        # ... compiling this compiles everything else necessary
        ['-d', bindir]  # put the binaries here
    )
    log.info("Executing command: {}".format(cmdargs))
    subprocess.check_call(cmdargs)


if __name__ == '__main__':
    main()
