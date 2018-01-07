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

Once installed from a Debian package, wkhtmltopdf will show up in "dpkg --list"
as "wkhtmltox". So you can remove it with
    sudo dpkg --remove wkhtmltox  # Debian

Examples of platform.linux_distribution():
    ('Ubuntu', '14.04', 'trusty')
    ('CentOS', '6.5', 'Final')
"""

import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request

import distro

if sys.version_info[0] < 3:
    raise AssertionError("Need Python 3")
if not platform.system() == 'Linux':
    raise AssertionError("Need Linux")

# =============================================================================
# What version do we have/need?
# =============================================================================

MAJOR_VERSION = "0.12"
MINOR_VERSION = "0.12.2.1"

INTENDED_VERSION = "wkhtmltopdf {} (with patched qt)".format(MINOR_VERSION)

existing_cmd = shutil.which('wkhtmltopdf')
if existing_cmd:
    print("existing wkhtmltopdf is {}".format(existing_cmd))
    proc = subprocess.Popen([existing_cmd, '--version'],
                            stdout=subprocess.PIPE)
    out, err = proc.communicate()
    existing_version = out.decode('ascii').strip()
    print("existing version: {}".format(existing_version))
    if existing_version == INTENDED_VERSION:
        print("wkhtmltopdf {} already installed".format(MINOR_VERSION))
        sys.exit(0)

# =============================================================================
# Basic distro rules
# =============================================================================

LINUX_DIST, LINUX_VERSION, LINUX_ID = distro.linux_distribution()
LINUX_DIST = LINUX_DIST.lower()

BITS_64 = platform.architecture()[0] == '64bit'

if LINUX_DIST in ('ubuntu', 'debian'):
    if not shutil.which('gdebi'):
        raise AssertionError("Need gdebi (try: sudo apt-get install gdebi)")
    installer = ['sudo', 'gdebi']
    extension = 'deb'
elif LINUX_DIST in ('fedora', 'rhel', 'centos'):
    if not shutil.which('yum'):
        raise AssertionError("Need yum")
    # installer = ['sudo', 'rpm', '-U']  # -U upgrade, equivalent to -i install
    installer = ['yum', '--nogpgcheck', 'localinstall']
    # ... http://stackoverflow.com/questions/13876875
    extension = 'rpm'
else:
    raise AssertionError("Unsupported Linux distribution")

# =============================================================================
# Establish URL
# =============================================================================

if BITS_64:
    arch = 'amd64'
else:
    arch = 'i386'

if LINUX_DIST == 'ubuntu':
    if LINUX_VERSION == 'precise':
        distro = 'precise'
    else:
        distro = 'trusty'
elif LINUX_DIST == 'centos':
    if LINUX_VERSION == '5' or LINUX_VERSION.startswith('5.'):
        distro = 'centos5'
    elif LINUX_VERSION == '6' or LINUX_VERSION.startswith('6.'):
        distro = 'centos6'
    else:
        distro = 'centos7'
        arch = 'amd64'
else:
    distro = 'UNKNOWN'

url_stem = (
    'http://download.gna.org/wkhtmltopdf/{MAJOR_VERSION}/'
    '{MINOR_VERSION}/'.format(
        MAJOR_VERSION=MAJOR_VERSION,
        MINOR_VERSION=MINOR_VERSION,
    )
)
filename = (
    'wkhtmltox-{MINOR_VERSION}_linux-{distro}-{arch}.{extension}'.format(
        MINOR_VERSION=MINOR_VERSION,
        distro=distro,
        arch=arch,
        extension=extension,
    )
)
url = url_stem + filename

# =============================================================================
# Download and install
# =============================================================================

with tempfile.TemporaryDirectory() as tmpdirname:
    localfilename = os.path.join(tmpdirname, filename)

    print("Downloading {} -> {}".format(url, localfilename))
    req = urllib.request.urlopen(url)
    with open(localfilename, 'wb') as f:
        f.write(req.read())

    print("Installing {}".format(localfilename))
    subprocess.check_call(installer + [localfilename])
