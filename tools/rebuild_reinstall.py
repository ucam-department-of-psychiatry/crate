#!/usr/bin/env python

"""
tools/rebuild_reinstall.py

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

1. Rebuild the package.
2. Remove the CRATE Debian package.
3. Reinstall the package.

"""

import os
import subprocess
from crate_anon.version import CRATE_VERSION  # , VERSION_DATE

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_ROOT = os.path.abspath(os.path.join(THIS_DIR, os.pardir))
PACKAGE_DIR = os.path.join(SOURCE_ROOT, "built_packages")
PACKAGE = 'crate'
DEBVERSION = '{}-1'.format(CRATE_VERSION)
PACKAGEFILE = os.path.join(
    PACKAGE_DIR,
    '{PACKAGE}_{DEBVERSION}_all.deb'.format(PACKAGE=PACKAGE,
                                            DEBVERSION=DEBVERSION))

subprocess.check_call([os.path.join(THIS_DIR, 'make_package.py')])
subprocess.check_call(['sudo', 'apt-get', '--yes', 'remove', PACKAGE])
subprocess.check_call(['sudo', 'gdebi', '--non-interactive', PACKAGEFILE])
