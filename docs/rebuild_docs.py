#!/usr/bin/env python

"""
docs/rebuild_docs.py

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

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

import os
import shutil
import subprocess

# Work out directories
THIS_DIR = os.path.dirname(os.path.realpath(__file__))
BUILD_HTML_DIR = os.path.join(THIS_DIR, "build", "html")

DEST_DIRS = []

if __name__ == '__main__':
    # Remove anything old
    for destdir in [BUILD_HTML_DIR] + DEST_DIRS:
        print(f"Deleting directory {destdir!r}")
        shutil.rmtree(destdir, ignore_errors=True)

    # Build docs
    print("Making HTML version of documentation")
    os.chdir(THIS_DIR)
    subprocess.call(["make", "html"])

    # Copy
    for destdir in DEST_DIRS:
        print(f"Copying {BUILD_HTML_DIR!r} -> {destdir!r}")
        shutil.copytree(BUILD_HTML_DIR, destdir)
