#!/usr/bin/env python
# crate/tools/rebuild_reinstall.py

import os
import subprocess
from crate_anon.version import VERSION  # , VERSION_DATE

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_ROOT = os.path.abspath(os.path.join(THIS_DIR, os.pardir))
PACKAGE_DIR = os.path.join(SOURCE_ROOT, "built_packages")
PACKAGE = 'crate'
DEBVERSION = '{}-1'.format(VERSION)
PACKAGEFILE = os.path.join(
    PACKAGE_DIR,
    '{PACKAGE}_{DEBVERSION}_all.deb'.format(PACKAGE=PACKAGE,
                                            DEBVERSION=DEBVERSION))

subprocess.check_call(['sudo', 'apt-get', '--yes', 'remove', PACKAGE])
subprocess.check_call([os.path.join(THIS_DIR, 'make_package.py')])
subprocess.check_call(['sudo', 'gdebi', '--non-interactive', PACKAGEFILE])
