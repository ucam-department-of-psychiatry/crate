#!/usr/bin/env python
# crate_anon/nlp_manager/build_medex_java_interface.py

"""
Script to compile Java source for CrateMedexPipeline

Author: Rudolf Cardinal
Copyright (C) 2015-2016 Rudolf Cardinal.
License: http://www.apache.org/licenses/LICENSE-2.0
"""

import argparse
import logging
import os
import subprocess
import tempfile

from crate_anon.common.fileops import moveglob, rmglob
from crate_anon.common.logsupport import configure_logger_for_colour
from crate_anon.nlp_manager.constants import (
    MEDEX_PIPELINE_CLASSNAME,
    MEDEX_DATA_READY_SIGNAL,
    MEDEX_RESULTS_READY_SIGNAL,
)


log = logging.getLogger(__name__)

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BUILD_DIR = os.path.join(THIS_DIR, 'compiled_nlp_classes')
SOURCE_FILE = os.path.join(THIS_DIR, MEDEX_PIPELINE_CLASSNAME + '.java')
DEFAULT_MEDEX_DIR = os.path.join(os.path.expanduser('~'), 'dev',
                                 'Medex_UIMA_1.3.6')
DEFAULT_JAVA = 'java'
DEFAULT_JAVAC = 'javac'


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compile Java classes for CRATE's interface to MedEx-UIMA")
    parser.add_argument(
        '--builddir', default=DEFAULT_BUILD_DIR,
        help="Output directory for compiled .class files (default: {})".format(
            DEFAULT_BUILD_DIR))
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
    parser.add_argument('--verbose', '-v', action='count', default=0,
                        help="Be verbose (use twice for extra verbosity)")
    parser.add_argument(
        '--launch', action='store_true',
        help="Launch script in demonstration mode (having previously "
             "compiled it)")
    args = parser.parse_args()

    loglevel = logging.DEBUG if args.verbose >= 1 else logging.INFO
    rootlogger = logging.getLogger()
    configure_logger_for_colour(rootlogger, level=loglevel)

    medexclasses = os.path.join(args.medexdir, 'bin')
    medexlibjars = os.path.join(args.medexdir, 'lib', '*')
    classpath = os.pathsep.join([args.builddir, medexclasses, medexlibjars])
    classpath_options = ['-classpath', classpath]

    if args.launch:
        inputdir = tempfile.TemporaryDirectory()
        outputdir = tempfile.TemporaryDirectory()
        prog_args = [
            "-data_ready_signal", MEDEX_DATA_READY_SIGNAL,
            "-results_ready_signal", MEDEX_RESULTS_READY_SIGNAL,
            "-i", inputdir.name,
            "-o", outputdir.name,
        ]
        if args.verbose > 0:
            prog_args += ['-v', '-v']
        cmdargs = (
            [args.java] +
            classpath_options +
            [MEDEX_PIPELINE_CLASSNAME] +
            prog_args
        )
        log.info("Executing command: {}".format(cmdargs))
        subprocess.check_call(cmdargs)
    else:
        cmdargs = (
            [args.javac, '-Xlint:unchecked'] +
            (['-verbose'] if args.verbose > 0 else []) +
            classpath_options +
            [SOURCE_FILE]
        )
        log.info("Executing command: {}".format(cmdargs))
        subprocess.check_call(cmdargs)
        os.makedirs(args.builddir, exist_ok=True)
        rmglob(os.path.join(args.builddir, '*.class'))
        moveglob(os.path.join(THIS_DIR, '*.class'), args.builddir)
        log.info("Output *.class files are in {}".format(args.builddir))


if __name__ == '__main__':
    main()
