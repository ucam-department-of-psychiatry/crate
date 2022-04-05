#!/usr/bin/env python

"""
docs/rebuild_docs.py

===============================================================================

    Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).

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

from typing import List

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger

log = logging.getLogger(__name__)


# Work out directories
THIS_DIR = os.path.dirname(os.path.realpath(__file__))
BUILD_HTML_DIR = os.path.join(THIS_DIR, "build", "html")

DEST_DIRS = []  # type: List[str]


if __name__ == "__main__":
    main_only_quicksetup_rootlogger()
    # Remove anything old
    for destdir in [BUILD_HTML_DIR] + DEST_DIRS:
        print(f"Deleting directory {destdir!r}")
        shutil.rmtree(destdir, ignore_errors=True)

    # Build docs
    print("Making HTML version of documentation")
    os.chdir(THIS_DIR)

    # When running from the GitHub action, it isn't possible to
    # download and build Medex automatically, so we just skip this
    # step.
    parser = argparse.ArgumentParser()
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

    recreate_args = [
        "python",
        os.path.join(THIS_DIR, "recreate_inclusion_files.py"),
    ]

    if args.skip_medex:
        recreate_args.append("--skip_medex")
    subprocess.check_call(recreate_args)

    cmdargs = ["make", "html"]
    if args.warnings_as_errors:
        cmdargs.append('SPHINXOPTS="-W"')

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

    # Copy
    for destdir in DEST_DIRS:
        print(f"Copying {BUILD_HTML_DIR!r} -> {destdir!r}")
        shutil.copytree(BUILD_HTML_DIR, destdir)
