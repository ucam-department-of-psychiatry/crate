#!/usr/bin/env python

"""
docs/rebuild_docs.py

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

**Rebuild all documentation.**

"""

import argparse
import logging
import os
import shutil
import subprocess
import sys
from typing import List

from rich_argparse import ArgumentDefaultsRichHelpFormatter

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger

log = logging.getLogger(__name__)


# Work out directories
THIS_DIR = os.path.dirname(os.path.realpath(__file__))
BUILD_HTML_DIR = os.path.join(THIS_DIR, "build", "html")

DEST_DIRS = []  # type: List[str]

EXIT_FAILURE = 1

if __name__ == "__main__":
    python_ok = sys.version_info.major >= 3 and sys.version_info.minor >= 10
    if not python_ok:
        log.error("You must run this script with Python 3.10 or later")
        sys.exit(EXIT_FAILURE)

    # -------------------------------------------------------------------------
    # Arguments
    # -------------------------------------------------------------------------
    # When running from the GitHub action, it isn't possible to
    # download and build Medex automatically, so we just skip this
    # step.
    parser = argparse.ArgumentParser(
        formatter_class=ArgumentDefaultsRichHelpFormatter
    )
    parser.add_argument(
        "--skip_inclusion_files",
        action="store_true",
        help="Don't rebuild inclusion files",
        default=False,
    )
    parser.add_argument(
        "--skip_medex",
        action="store_true",
        help="Don't try to build Medex help files",
        default=False,
    )
    parser.add_argument(
        "--warnings_as_errors",
        action="store_true",
        help="Treat warnings as errors",
    )
    args = parser.parse_args()

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------
    main_only_quicksetup_rootlogger(level=logging.INFO)

    # -------------------------------------------------------------------------
    # Remove anything old
    # -------------------------------------------------------------------------
    for destdir in [BUILD_HTML_DIR] + DEST_DIRS:
        print(f"Deleting directory {destdir!r}")
        shutil.rmtree(destdir, ignore_errors=True)

    # Build docs
    print("Making HTML version of documentation")
    os.chdir(THIS_DIR)

    # -------------------------------------------------------------------------
    # Recreate inclusion files
    # -------------------------------------------------------------------------

    recreate_args = [
        "python",
        os.path.join(THIS_DIR, "recreate_inclusion_files.py"),
    ]

    if args.skip_medex:
        recreate_args.append("--skip_medex")

    if not args.skip_inclusion_files:
        subprocess.check_call(recreate_args)

    # -------------------------------------------------------------------------
    # Make HTML docs
    # -------------------------------------------------------------------------

    cmdargs = ["make", "html"]
    sphinxopts = ["-T"]  # Show full traceback on error
    if args.warnings_as_errors:
        sphinxopts.append("-W")

    cmdargs.append(f'SPHINXOPTS={" ".join(sphinxopts)}')

    try:
        subprocess.check_call(cmdargs)
    except subprocess.CalledProcessError as e:
        log.debug(
            "\n\nTroubleshooting Sphinx/docutils errors:\n\n"
            "Document may not end with a transition\n"
            "--------------------------------------\n"
            "For auto-generated code docs, ensure there is a description "
            "beneath the row of '=' in the copyright block of the python "
            "file.\n"
        )

        raise e

    # -------------------------------------------------------------------------
    # Copy
    # -------------------------------------------------------------------------

    for destdir in DEST_DIRS:
        print(f"Copying {BUILD_HTML_DIR!r} -> {destdir!r}")
        shutil.copytree(BUILD_HTML_DIR, destdir)
