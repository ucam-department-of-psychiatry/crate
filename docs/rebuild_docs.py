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
import os
import shutil
import subprocess

from typing import List

# Work out directories
THIS_DIR = os.path.dirname(os.path.realpath(__file__))
BUILD_HTML_DIR = os.path.join(THIS_DIR, "build", "html")

DEST_DIRS = []  # type: List[str]

if __name__ == "__main__":
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
    parser.add_argument("--skip_medex", action="store_true",
                        help="Don't try to build Medex help files",
                        default=False)
    args = parser.parse_args()

    recreate_args = ["python",
                     os.path.join(THIS_DIR,
                                  "recreate_inclusion_files.py")]

    if args.skip_medex:
        recreate_args.append("--skip_medex")
    subprocess.check_call(recreate_args)

    # -W: Turn warnings into errors
    subprocess.check_call(["make", "html", 'SPHINXOPTS="-W"'])

    # Copy
    for destdir in DEST_DIRS:
        print(f"Copying {BUILD_HTML_DIR!r} -> {destdir!r}")
        shutil.copytree(BUILD_HTML_DIR, destdir)
