#!/usr/bin/env python

"""
crate_anon/nlp_manager/build_gate_java_interface.py

===============================================================================

    Copyright (C) 2015-2020 Rudolf Cardinal (rudolf@pobox.com).

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

**Script to compile Java source for CrateGatePipeline.**

"""

import argparse
import logging
import os
import subprocess
import sys

from cardinal_pythonlib.cmdline import cmdline_quote
from cardinal_pythonlib.logs import configure_logger_for_colour

from crate_anon.common.constants import EnvVar
from crate_anon.nlp_manager.constants import GATE_PIPELINE_CLASSNAME


log = logging.getLogger(__name__)

EXIT_FAILURE = 1

if EnvVar.GENERATING_CRATE_DOCS in os.environ:
    THIS_DIR = "/path/to/crate/crate_anon/nlp_manager"
    DEFAULT_GATE_DIR = "/path/to/GATE/installation"
else:
    THIS_DIR = os.path.dirname(os.path.abspath(__file__))
    DEFAULT_GATE_DIR = os.environ.get("GATE_HOME", "/")

DEFAULT_BUILD_DIR = os.path.join(THIS_DIR, 'compiled_nlp_classes')
SOURCE_FILE = os.path.join(THIS_DIR, GATE_PIPELINE_CLASSNAME + '.java')

DEFAULT_JAVA = 'java'
DEFAULT_JAVAC = 'javac'


def main() -> None:
    """
    Command-line processor. See command-line help.
    """
    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(
        description="Compile Java classes for CRATE's interface to GATE",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '--builddir', default=DEFAULT_BUILD_DIR,
        help="Output directory for compiled .class files")
    parser.add_argument(
        '--gatedir', default=DEFAULT_GATE_DIR,
        help="Root directory of GATE installation")
    parser.add_argument(
        '--gate_exec',
        help="Path to GATE executable. Temporary."
    )
    parser.add_argument(
        '--java', default=DEFAULT_JAVA,
        help="Java executable")
    parser.add_argument(
        '--javac', default=DEFAULT_JAVAC,
        help="Java compiler")
    parser.add_argument(
        '--verbose', '-v', action='count', default=0,
        help="Be verbose (use twice for extra verbosity)")
    parser.add_argument(
        '--launch', action='store_true',
        help="Launch script in demonstration mode (having previously "
             "compiled it)")
    args = parser.parse_args()

    loglevel = logging.DEBUG if args.verbose >= 1 else logging.INFO
    rootlogger = logging.getLogger()
    configure_logger_for_colour(rootlogger, level=loglevel)

    if not args.gate_exec:
        if not os.path.exists(args.gatedir):
            log.error(f"Could not find GATE installation at {args.gatedir}. "
                      f"Is GATE installed? Have you set --gatedir correctly?")
            sys.exit(EXIT_FAILURE)

        gatejar = os.path.join(args.gatedir, 'bin', 'gate.jar')
    else:
        gatejar = args.gate_exec

    gatelibjars = os.path.join(args.gatedir, 'lib', '*')
    classpath = os.pathsep.join([args.builddir, gatejar, gatelibjars])
    classpath_options = ['-classpath', classpath]

    if args.launch:
        features = ['-a', 'Person', '-a', 'Location']
        eol_options = ['-it', 'END', '-ot', 'END']
        prog_args = features + eol_options + ['--demo']
        if args.verbose > 0:
            prog_args += ['-v', '-v']
        if args.verbose > 1:
            prog_args += ['-wg', 'wholexml_', '-wa', 'annotxml_']
        cmdargs = (
            [args.java] +
            classpath_options +
            [GATE_PIPELINE_CLASSNAME] +
            prog_args
        )
        log.info(f"Executing command: {cmdline_quote(cmdargs)}")
        subprocess.check_call(cmdargs)
    else:
        os.makedirs(args.builddir, exist_ok=True)
        cmdargs = (
            [args.javac, '-Xlint:unchecked'] +
            (['-verbose'] if args.verbose > 0 else []) +
            classpath_options +
            ['-d', args.builddir] +
            [SOURCE_FILE]
        )
        log.info(f"Executing command: {cmdline_quote(cmdargs)}")
        subprocess.check_call(cmdargs)
        log.info(f"Output *.class files are in {args.builddir}")

    # JAR build and run
    # mkdir -p jarbuild

    # cd jarbuild
    # javac $JAVAC_OPTIONS ../CrateGatePipeline.java
    # for JARFILE in $GATEJAR $GATELIBJARS; do
    #     echo "Extracting from JAR: $JARFILE"
    #     jar xvf $JARFILE
    # done
    # mkdir -p META-INF
    # echo "Main-Class: CrateGatePipeline" > META-INF/MANIFEST.MF
    # CLASSES=`find . -name "*.class"`
    # jar cmvf META-INF/MANIFEST.MF ../gatehandler.jar $CLASSES
    # cd ..

    # This does work, but it can't find the gate.plugins.home, etc.,
    # so we gain little.

    # See also: http://one-jar.sourceforge.net/version-0.95/

    # Note that arguments *after* the program name are seen by the program, and
    # arguments before it go to Java. If you specify the classpath (which you
    # need to to find GATE), you must also include the directory of your
    # MyThing.class file.

    # JAR run:
    # java -jar ./gatehandler.jar $PROG_ARGS


if __name__ == '__main__':
    main()
