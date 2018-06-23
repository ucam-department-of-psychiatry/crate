#!/usr/bin/env python

"""
===============================================================================

    Copyright (C) 2015-2018 Rudolf Cardinal (rudolf@pobox.com).

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
from os.path import abspath, dirname, join, splitext
import shutil
import subprocess

CURRENT_DIR = dirname(abspath(__file__))
PROJECT_BASE_DIR = abspath(join(CURRENT_DIR, os.pardir))

FLAKE8 = shutil.which('flake8')
if not FLAKE8:
    raise AssertionError("Need flake8")

# http://stackoverflow.com/questions/19859840/excluding-directories-in-os-walk
exclude = ["migrations"]
for root, dirs, files in os.walk(PROJECT_BASE_DIR, topdown=True):
    dirs[:] = [d for d in dirs if d not in exclude]
    for f in files:
        filename, ext = splitext(f)
        if ext == '.py':
            filepath = join(root, f)
            subprocess.call([FLAKE8, "--ignore=T003", filepath])
