#!/usr/bin/env python

"""
tools/make_package.py

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

Make CRATE packages:

- Python, for PyPI and pip (named like ``dist/crate-anon-VERSION.tar.gz``)
- Debian (named like ``built_packages/crate_VERSION_all.deb``)

"""

import os
from os.path import join
import shutil
import subprocess
import sys
import tempfile

from cardinal_pythonlib.file_io import (
    get_lines_without_comments,
    remove_gzip_timestamp,
)
from cardinal_pythonlib.fileops import copy_tree_root, mkdir_p

from crate_anon.common.constants import EnvVar
from crate_anon.version import (
    CRATE_VERSION,
    CRATE_VERSION_DATE,
    MINIMUM_PYTHON_VERSION_AS_DECIMAL,
    require_minimum_python_version,
)
from crate_anon.crateweb.config.constants import CRATEWEB_CONFIG_ENV_VAR

require_minimum_python_version()


# =============================================================================
# Constants including defaults
# =============================================================================

PACKAGE_FOR_DEB = "crate"
PACKAGE_FOR_PYPI = "crate-anon"
PACKAGE_DIR_FROM_SOURCE_ROOT = "crate_anon"


CRATE_USER = "www-data"
CRATE_GROUP = "www-data"

MAKE_USER = False  # not working properly yet
MAKE_GROUP = False

DEFAULT_GUNICORN_PORT = 8005
DEFAULT_GUNICORN_SOCKET = "/tmp/.crate_gunicorn.sock"
# ... must be writable by the relevant user
# http://unix.stackexchange.com/questions/88083/idiomatic-location-for-file-based-sockets-on-debian-systems

LEAVE_TEMPORARY_WORKSPACE_BEHIND = False  # set to True for debugging

# =============================================================================
# Helper functions
# =============================================================================

FG_RED = "\033[0;31m"
BG_GREY = "\033[2;47m"
NO_COLOUR = "\033[0m"


def error(msg: str) -> None:
    """
    Prints an error with ANSI colour.
    """
    print(FG_RED, BG_GREY, msg, NO_COLOUR, sep="")


def workpath(destpath: str, *args: str) -> str:
    """
    Creates a workpath by embedding destpath (and any args) within WORK_DIR.
    """
    workdir = WORK_DIR
    assert workdir
    if destpath[0] == os.sep:  # destpath begins with "/"; remove that
        return join(workdir, destpath[1:], *args)
    else:
        return join(workdir, destpath, *args)


BASHFUNC = r"""

#------------------------------------------------------------------------------
# Helper functions
#------------------------------------------------------------------------------

command_exists()
{
    # arguments: $1 is the command to test
    # returns 0 (true) for found, 1 (false) for not found
    if command -v $1 >/dev/null; then return 0; else return 1; fi
}

running_centos()
{
    if [ -f /etc/system-release ] ; then
        SYSTEM=`cat /etc/system-release | cut -d' ' -f1`
        # VERSION=`cat /etc/system-release | cut -d' ' -f3`
        # SYSTEM_ID=\$SYSTEM-\$VERSION
        if ["$SYSTEM" == "CentOS"] ; then
            return 0  # true
        fi
    fi
    return 1  # false
}

service_exists()
{
    # arguments: $1 is the service being tested

    # Older Ubuntu:
    if service $1 status 2>&1 | grep "unrecognized service" >/dev/null ; then
        return 1  # false
    fi
    # Ubuntu 16.04:
    if service $1 status 2>&1 | grep "not-found" >/dev/null ; then
        return 1  # false
    fi
    return 0  # true
}

service_supervisord_command()
{
    # The exact supervisor program name is impossible to predict (e.g. in
    # "supervisorctl stop MYTASKNAME"), so we just start/stop everything.
    # Ubuntu: service supervisor
    # CentOS: service supervisord

    cmd=$1
    if service_exists supervisord ; then
        echo "Executing: service supervisord $cmd"
        service supervisord $cmd || echo "Can't $cmd supervisord"
    else
        if service_exists supervisor ; then
            echo "Executing: service supervisor $cmd"
            service supervisor $cmd || echo "Can't $cmd supervisor"
        else
            echo "Don't know which supervisor/supervisord service to $cmd"
        fi
    fi
}

stop_supervisord()
{
    service_supervisord_command stop
}

restart_supervisord()
{
    service_supervisord_command restart
}

"""


# =============================================================================
# Check prerequisites
# =============================================================================
# https://stackoverflow.com/questions/2806897

if os.geteuid() == 0:
    exit("This script should not be run using sudo or as the root user")

print("Checking prerequisites")
PREREQUISITES = ["dpkg-deb"]
for cmd in PREREQUISITES:
    if shutil.which(cmd) is None:
        error(f"{cmd} command not found; stopping")
        sys.exit(1)


# =============================================================================
# Constants
# =============================================================================

# -----------------------------------------------------------------------------
# Software
# -----------------------------------------------------------------------------

PYTHON_WITH_VER = f"python{MINIMUM_PYTHON_VERSION_AS_DECIMAL}"

# -----------------------------------------------------------------------------
# Directory constants
# -----------------------------------------------------------------------------

# Source
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_ROOT = os.path.abspath(join(THIS_DIR, os.pardir))
EGG_DIR = join(SOURCE_ROOT, "crate_anon.egg-info")
PACKAGE_DIR = join(SOURCE_ROOT, "built_packages")

# Destination, as seen on the final system
DEST_ROOT = join("/usr/share", PACKAGE_FOR_DEB)
DEST_VIRTUALENV = join(DEST_ROOT, "crate_virtualenv")
DEST_CRATE_ROOT = join(
    DEST_VIRTUALENV,
    "lib",
    PYTHON_WITH_VER,
    "site-packages",
    PACKAGE_DIR_FROM_SOURCE_ROOT,
)
DEST_DJANGO_ROOT = join(DEST_CRATE_ROOT, "crateweb")
# Lintian dislikes files/subdirectories in: /usr/bin/X, /usr/local/X, /opt/X
# It dislikes images in /usr/lib
DEST_PACKAGE_CONF_DIR = join("/etc", PACKAGE_FOR_DEB)
DEST_SUPERVISOR_CONF_DIR = "/etc/supervisor/conf.d"
INFO_DEST_DPKG_DIR = "/var/lib/dpkg/info"  # not written to directly
DEST_DOC_DIR = join("/usr/share/doc", PACKAGE_FOR_DEB)
DEST_COLLECTED_STATIC_DIR = join(DEST_DJANGO_ROOT, "static_collected")
DEST_PYTHON_CACHE = join(DEST_ROOT, ".cache")

# Working/Debian
WORK_DIR = tempfile.mkdtemp()
print("Using working directory: " + WORK_DIR)
DEB_DIR = workpath("DEBIAN")  # where Debian package control information lives
DEB_OVERRIDE_DIR = workpath("/usr/share/lintian/overrides")

WORK_ROOT = workpath(DEST_ROOT)

# -----------------------------------------------------------------------------
# Version number etc.
# -----------------------------------------------------------------------------

DEBVERSION = f"{CRATE_VERSION}-1"
PACKAGENAME = join(PACKAGE_DIR, f"{PACKAGE_FOR_DEB}_{DEBVERSION}_all.deb")
print(
    f"Building .deb package for {PACKAGE_FOR_DEB} version "
    f"{CRATE_VERSION} ({CRATE_VERSION_DATE})"
)
CRATE_PIPFILE = f"{PACKAGE_FOR_PYPI}-{CRATE_VERSION}.tar.gz"

# -----------------------------------------------------------------------------
# Files
# -----------------------------------------------------------------------------

DEB_REQUIREMENTS_FILE = join(SOURCE_ROOT, "requirements-ubuntu.txt")
SPECIMEN_SUPERVISOR_CONF_FILE = join(
    DEST_ROOT, "specimen_etc_supervisor_conf.d_crate.conf"
)
DEST_SUPERVISOR_CONF_FILE = join(
    DEST_SUPERVISOR_CONF_DIR, f"{PACKAGE_FOR_DEB}.conf"
)
DEB_PACKAGE_FILE = join(PACKAGE_DIR, f"{PACKAGE_FOR_DEB}_{DEBVERSION}_all.deb")
LOCAL_CONFIG_BASENAME = "crateweb_local_settings.py"
DEST_CRATEWEB_CONF_FILE = join(DEST_PACKAGE_CONF_DIR, LOCAL_CONFIG_BASENAME)
INSTRUCTIONS = join(DEST_ROOT, "instructions.txt")
DEST_VENV_INSTALLER = join(DEST_ROOT, "tools", "install_virtualenv.py")
DEST_WKHTMLTOPDF_INSTALLER = join(DEST_ROOT, "tools", "install_wkhtmltopdf.py")
DEST_CRATE_PIPFILE = join(DEST_ROOT, CRATE_PIPFILE)

# =============================================================================
# Make directories
# =============================================================================

print("Making directories")
mkdir_p(WORK_DIR)
mkdir_p(workpath(DEST_ROOT))
mkdir_p(workpath(DEST_PACKAGE_CONF_DIR))
mkdir_p(workpath(DEST_SUPERVISOR_CONF_DIR))
mkdir_p(workpath(DEST_DOC_DIR))
mkdir_p(DEB_DIR)
mkdir_p(DEB_OVERRIDE_DIR)

# =============================================================================
# Make Debian files
# =============================================================================

# -----------------------------------------------------------------------------
print(
    "Creating preinst file. Will be installed as "
    + join(INFO_DEST_DPKG_DIR, PACKAGE_FOR_DEB + ".preinst")
)
# -----------------------------------------------------------------------------
with open(join(DEB_DIR, "preinst"), "w") as outfile:
    # NB "#!/usr/bin/env bash" is refused by Lintian; it gives errors like
    # "unknown-control-interpreter" and "forbidden-postrm-interpreter".
    # On Debian, Bash is always /bin/bash.
    # See also
    # https://stackoverflow.com/questions/10376206/what-is-the-preferred-bash-shebang  # noqa
    print(
        f"""#!/bin/bash
set -e  # Exit on any errors. (Lintian strongly advises this.)

{BASHFUNC}

echo '{PACKAGE_FOR_DEB}: preinst file executing'

stop_supervisord

echo '{PACKAGE_FOR_DEB}: preinst file finished'

    """,
        file=outfile,
    )

# -----------------------------------------------------------------------------
print(
    "Creating postinst file. Will be installed as "
    + join(INFO_DEST_DPKG_DIR, PACKAGE_FOR_DEB + ".postinst")
)
# -----------------------------------------------------------------------------

if MAKE_GROUP:
    MAKE_GROUP_COMMAND_1 = f"echo '=== Adding group {CRATE_GROUP}'"
    # MAKE_GROUP_COMMAND_2 = f"addgroup --system {CRATE_GROUP}"
    MAKE_GROUP_COMMAND_2 = f"addgroup {CRATE_GROUP}"
else:
    MAKE_GROUP_COMMAND_1 = "# No need to add user"
    MAKE_GROUP_COMMAND_2 = ""
if MAKE_USER:
    MAKE_USER_COMMAND_1 = (
        f"echo '=== Adding system user {CRATE_USER} in group {CRATE_GROUP}'"
    )
    # MAKE_USER_COMMAND_2 = (
    #     f"adduser --system --ingroup {CRATE_GROUP} "
    #     f"--home /home/{CRATE_USER} {CRATE_USER}")
    MAKE_USER_COMMAND_2 = (
        f"adduser --system --ingroup {CRATE_GROUP} {CRATE_USER}"
    )
    # MAKE_USER_COMMAND_2 = f"adduser --ingroup {CRATE_GROUP} {CRATE_USER}"
    # https://lintian.debian.org/tags/maintainer-script-should-not-use-adduser-system-without-home.html  # noqa
    # http://unix.stackexchange.com/questions/47880/how-debian-package-should-create-user-accounts  # noqa
else:
    MAKE_USER_COMMAND_1 = "# No need to add user"
    MAKE_USER_COMMAND_2 = ""

with open(join(DEB_DIR, "postinst"), "w") as outfile:
    # See above re Lintian and shebangs.
    print(
        rf"""#!/bin/bash
# Exit on any errors? (Lintian strongly advises this.)
set -e
{BASHFUNC}
echo '{PACKAGE_FOR_DEB}: postinst file executing'

# -----------------------------------------------------------------------------
# Make users/groups
# -----------------------------------------------------------------------------
{MAKE_GROUP_COMMAND_1}
{MAKE_GROUP_COMMAND_2}
{MAKE_USER_COMMAND_1}
{MAKE_USER_COMMAND_2}

# -----------------------------------------------------------------------------
echo "Setting ownership"
# -----------------------------------------------------------------------------

# Lintian dislikes this:
# chown -R {CRATE_USER}:{CRATE_GROUP} {DEST_ROOT}
# ... it says maintainer-script-should-not-use-recursive-chown-or-chmod

chown {CRATE_USER}:{CRATE_GROUP} {DEST_SUPERVISOR_CONF_FILE}
chown {CRATE_USER}:{CRATE_GROUP} {DEST_CRATEWEB_CONF_FILE}

# -----------------------------------------------------------------------------
echo "Installing virtual environment and package..."
# -----------------------------------------------------------------------------
# Note the need to set XDG_CACHE_HOME, or pip will use the wrong user's
# $HOME variable.
sudo \
    --user={CRATE_USER} \
    XDG_CACHE_HOME={DEST_PYTHON_CACHE} \
    {PYTHON_WITH_VER} \
    "{DEST_VENV_INSTALLER}" "{DEST_VIRTUALENV}" "{DEST_CRATE_PIPFILE}"
    # --skippackagechecks
echo "... finished installing virtual environment"

# -----------------------------------------------------------------------------
echo "Installing package to venv and collecting static files"
# -----------------------------------------------------------------------------
source "{DEST_VIRTUALENV}/bin/activate"
# Run temporarily without local settings file (since the default raises an
# exception):
export {EnvVar.RUN_WITHOUT_CONFIG}=true
crate_django_manage collectstatic --noinput
deactivate

# -----------------------------------------------------------------------------
# Restart supervisor process(es)
# -----------------------------------------------------------------------------
restart_supervisord

echo "========================================================================"
echo "-   Can't install wkhtmltopdf right now (dpkg database will be locked)."
echo "    Later, run this once:"
echo "    sudo {PYTHON_WITH_VER} {DEST_WKHTMLTOPDF_INSTALLER}"
echo "========================================================================"

echo '{PACKAGE_FOR_DEB}: postinst file finished'

echo
echo "Please read this file: {INSTRUCTIONS}"
echo
    """,
        file=outfile,
    )

# -----------------------------------------------------------------------------
print(
    "Creating prerm file. Will be installed as "
    + join(INFO_DEST_DPKG_DIR, PACKAGE_FOR_DEB + ".prerm")
)
# -----------------------------------------------------------------------------
with open(join(DEB_DIR, "prerm"), "w") as outfile:
    # See above re Lintian and shebangs.
    print(
        f"""#!/bin/bash
set -e
{BASHFUNC}
echo '{PACKAGE_FOR_DEB}: prerm file executing'

stop_supervisord
rm -rf {DEST_VIRTUALENV}

echo '{PACKAGE_FOR_DEB}: prerm file finished'
    """,
        file=outfile,
    )

# -----------------------------------------------------------------------------
print(
    "Creating postrm file. Will be installed as "
    + join(INFO_DEST_DPKG_DIR, PACKAGE_FOR_DEB + ".postrm")
)
# -----------------------------------------------------------------------------
with open(join(DEB_DIR, "postrm"), "w") as outfile:
    # See above re Lintian and shebangs.
    print(
        f"""#!/bin/bash
set -e
{BASHFUNC}
echo '{PACKAGE_FOR_DEB}: postrm file executing'

restart_supervisord

echo '{PACKAGE_FOR_DEB}: postrm file finished'
    """,
        file=outfile,
    )

# -----------------------------------------------------------------------------
print("Creating control file")
# -----------------------------------------------------------------------------
DEPENDS_DEB = get_lines_without_comments(DEB_REQUIREMENTS_FILE)
if MAKE_GROUP or MAKE_USER:
    DEPENDS_DEB.append("adduser")
with open(join(DEB_DIR, "control"), "w") as outfile:
    print(
        f"""Package: {PACKAGE_FOR_DEB}
Version: {DEBVERSION}
Section: science
Priority: optional
Architecture: all
Maintainer: Rudolf Cardinal <rudolf@pobox.com>
Depends: {", ".join(DEPENDS_DEB)}
Recommends: mysql-workbench
Description: Clinical Records Anonymisation and Text Extraction (CRATE).
 CRATE allows you to do the following:
 (1) Anonymise a relational database.
 (2) Run external natural language processing (NLP) tools over a database.
 (3) Provide a research web front end.
 (4) Manage a consent-to-contact framework that's anonymous to researchers.
""",
        file=outfile,
    )

# -----------------------------------------------------------------------------
print(
    "Creating conffiles file. Will be installed as "
    + join(INFO_DEST_DPKG_DIR, PACKAGE_FOR_DEB + ".conffiles")
)
# -----------------------------------------------------------------------------
configfiles = [DEST_CRATEWEB_CONF_FILE, DEST_SUPERVISOR_CONF_FILE]
with open(join(DEB_DIR, "conffiles"), "w") as outfile:
    print("\n".join(configfiles), file=outfile)
# If a configuration file is removed by the user, it won't be reinstalled:
#   http://www.debian.org/doc/debian-policy/ap-pkg-conffiles.html
# In this situation, do "sudo aptitude purge crate" then reinstall.

# -----------------------------------------------------------------------------
print("Creating Lintian override file")
# -----------------------------------------------------------------------------
with open(join(DEB_OVERRIDE_DIR, PACKAGE_FOR_DEB), "w") as outfile:
    print(
        f"""
# Not an official new Debian package, so ignore this one.
# If we did want to close a new-package ITP bug:
# http://www.debian.org/doc/manuals/developers-reference/pkgs.html#upload-bugfix  # noqa
{PACKAGE_FOR_DEB} binary: new-package-should-close-itp-bug
{PACKAGE_FOR_DEB} binary: extra-license-file
{PACKAGE_FOR_DEB} binary: embedded-javascript-library
{PACKAGE_FOR_DEB} binary: non-standard-file-perm
    """,
        file=outfile,
    )

# -----------------------------------------------------------------------------
print(
    "Creating copyright file. Will be installed as "
    + join(DEST_DOC_DIR, "copyright")
)
# -----------------------------------------------------------------------------
with open(workpath(DEST_DOC_DIR, "copyright"), "w") as outfile:
    print(
        f"""{PACKAGE_FOR_DEB}

CRATE

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

    See also /usr/share/common-licenses

ADDITIONAL LIBRARY COMPONENTS

    Public domain or copyright (C) their respective authors (for details,
    see attribution in the source code and other license terms packaged with
    the source).

    """,
        file=outfile,
    )
# ... reference to /usr/share/common-licenses is required by Lintian;
# https://lintian.debian.org/tags/copyright-should-refer-to-common-license-file-for-gpl.html  # noqa

# =============================================================================
# Destination files
# =============================================================================

print("Creating destination files")

# -----------------------------------------------------------------------------
print(
    f"Creating {DEST_SUPERVISOR_CONF_FILE} and "
    f"{SPECIMEN_SUPERVISOR_CONF_FILE}"
)
# -----------------------------------------------------------------------------
# Don't use a gunicorn_start script like this one:
#   http://michal.karzynski.pl/blog/2013/06/09/django-nginx-gunicorn-virtualenv-supervisor/
# ... it doesn't work (supervisord doesn't stop it properly)
# Just use the supervisor conf file.
with open(workpath(SPECIMEN_SUPERVISOR_CONF_FILE), "w") as outfile:
    # noinspection PyPep8
    print(
        f"""

; IF YOU EDIT THIS FILE, run:
;       sudo service supervisor restart
; TO MONITOR SUPERVISOR, run:
;       sudo service supervisorctl status
; NOTES:
; - You can't put quotes around the directory variable
;   https://stackoverflow.com/questions/10653590
; - Programs like celery and gunicorn that are installed within a virtual
;   environment use the virtualenv's python via their shebang.

[program:crate-celery-worker]

command = {DEST_VIRTUALENV}/bin/celery worker --app=crate_anon.crateweb.consent --loglevel=info
directory = {DEST_DJANGO_ROOT}
environment = {CRATEWEB_CONFIG_ENV_VAR}="{DEST_CRATEWEB_CONF_FILE}"
# ... no longer used: PYTHONPATH="{DEST_ROOT}"
user = {CRATE_USER}
stdout_logfile = /var/log/supervisor/{PACKAGE_FOR_DEB}_celery.log
stderr_logfile = /var/log/supervisor/{PACKAGE_FOR_DEB}_celery_err.log
autostart = true
autorestart = true
startsecs = 10
stopwaitsecs = 600

[program:crate-gunicorn]

command = {DEST_VIRTUALENV}/bin/gunicorn crate_anon.crateweb.config.wsgi:application --workers 4 --bind=unix:{DEFAULT_GUNICORN_SOCKET}
; Alternative methods (port and socket respectively):
;   --bind=127.0.0.1:{DEFAULT_GUNICORN_PORT}
;   --bind=unix:{DEFAULT_GUNICORN_SOCKET}
directory = {DEST_DJANGO_ROOT}
# ... Gunicorn/Django is VERY FUSSY ABOUT ITS DIRECTORY, even with absolute package names; "config" must work as a bare import
environment = {CRATEWEB_CONFIG_ENV_VAR}="{DEST_CRATEWEB_CONF_FILE}"
# ... no longer used: PYTHONPATH="{DEST_ROOT}"
user = {CRATE_USER}
stdout_logfile = /var/log/supervisor/{PACKAGE_FOR_DEB}_gunicorn.log
stderr_logfile = /var/log/supervisor/{PACKAGE_FOR_DEB}_gunicorn_err.log
autostart = true
autorestart = true
startsecs = 10
stopwaitsecs = 60

    """,  # noqa:E501
        file=outfile,
    )


# -----------------------------------------------------------------------------
print("Creating " + INSTRUCTIONS)
# -----------------------------------------------------------------------------
with open(workpath(INSTRUCTIONS), "w") as outfile:
    # noinspection PyPep8
    print(
        f"""
..

===============================================================================
Your system's CRATE configuration
===============================================================================
- Default CRATE config is:
    {DEST_CRATEWEB_CONF_FILE}
  This must be edited before it will run properly.

- Gunicorn/Celery are being supervised as per:
    {DEST_SUPERVISOR_CONF_FILE}
  This this should be edited to point to the correct CRATE config.
  (And copied, in the unlikely event you should want to run >1 instance.)

- Gunicorn default port is:
    {DEFAULT_GUNICORN_PORT}
  To change this, edit
    {DEST_SUPERVISOR_CONF_FILE}
  Copy this script to run another instance on another port.

- Static file root to serve:
    {DEST_COLLECTED_STATIC_DIR}
  See instructions below re Apache.

===============================================================================
Command-line use: Django development server
===============================================================================
For convenience:

    export CRATE_VIRTUALENV="{DEST_VIRTUALENV}"

To activate virtual environment:
    source "$CRATE_VIRTUALENV/bin/activate"

Then use crate_django_manage as the Django management tool.
Once you've activated the virtual environment, you can do this for a demo
server:
    crate_django_manage runserver

Its default port will be 8000.

To deactivate the virtual environment:
    deactivate

===============================================================================
Full stack
===============================================================================

- Gunicorn serves CRATE via WSGI
  ... serving via an internal port (in the default configuration, {DEFAULT_GUNICORN_PORT}).

- Celery talks to CRATE (in the web "foreground" and in the background)

- RabbitMQ handles messaging for Celery

- supervisord keeps Gunicorn and Celery running

- You should use a proper web server like Apache or nginx to:

    (a) serve static files
        ... offer URL: <your_crate_app_path>/static
        ... from filesystem: {DEST_COLLECTED_STATIC_DIR}

    (b) proxy requests to the WSGI app via Gunicorn's internal port

===============================================================================
Monitoring with supervisord
===============================================================================

    sudo supervisorctl  # assuming it's running as root

===============================================================================
Apache
===============================================================================
-------------------------------------------------------------------------------
OPTIMAL: proxy Apache through to Gunicorn
-------------------------------------------------------------------------------
(a) Add Ubuntu/Apache prerequisites

    sudo apt-get install apache2 libapache2-mod-proxy-html libapache2-mod-xsendfile
    sudo a2enmod proxy_http

(b) Configure Apache for CRATE.
    Use a section like this in the Apache config file:

<VirtualHost *:443>
    # ...

    # =========================================================================
    # CRATE
    # =========================================================================

    # We will mount the CRATE app at /crate/ and /crate_static/, and compel
    # it to run over HTTPS, as follows.

        # ---------------------------------------------------------------------
        # 1. Proxy requests to the Gunicorn server and back, and allow access
        # ---------------------------------------------------------------------
        #    ... either via port {DEFAULT_GUNICORN_PORT}
        #    ... or, better, via socket {DEFAULT_GUNICORN_SOCKET}
        # NOTES
        # - Don't specify trailing slashes.
        #   If you do, http://host/crate will fail though;
        #              http://host/crate/ will succeed.
        # - Using a socket
        #   - this requires Apache 2.4.9, and passes after the '|' character a
        #     URL that determines the Host: value of the request; see
        #       https://httpd.apache.org/docs/trunk/mod/mod_proxy.html#proxypass
        #   - The Django debug toolbar will then require the bizarre entry in
        #     the Django settings: INTERNAL_IPS = ("b''", ) -- i.e. the string
        #     value of "b''", not an empty bytestring.
        # - Ensure that you put the CORRECT PROTOCOL (e.g. https) in the rules
        #   below.

        # Port
        # Note the use of "http" (reflecting the backend), not https (like the
        # front end).
    # ProxyPass /crate https://127.0.0.1:{DEFAULT_GUNICORN_PORT}
    # ProxyPassReverse /crate https://127.0.0.1:{DEFAULT_GUNICORN_PORT}
        # Socket (Apache 2.4.9 and higher)
    ProxyPass /crate unix:{DEFAULT_GUNICORN_SOCKET}|https://localhost
    ProxyPassReverse /crate unix:{DEFAULT_GUNICORN_SOCKET}|https://localhost
        # Allow access
    <Location /crate>
        Require all granted
    </Location>

        # ---------------------------------------------------------------------
        # 2. Serve static files
        # ---------------------------------------------------------------------
        # a) offer them at the appropriate URL
        #    This MUST match Django's STATIC_URL, which is set to
        #    '/crate_static/' in config/settings.py, but can be overridden in
        #    your user-defined CRATE config file (passed to the Gunicorn and
        #    Celery processes)/
        # b) provide permission

    Alias /crate_static/ {DEST_COLLECTED_STATIC_DIR}/
    <Directory {DEST_COLLECTED_STATIC_DIR}>
        Require all granted
    </Directory>

        # If you want your logo to be visible in the dev_admin test view,
        # then make this enable access to the URL you specified as
        # PDF_LOGO_ABS_URL in the config:

    Alias /crate_logo {DEST_DJANGO_ROOT}/static/demo_logo/logo_cpft.png
    <Location /crate_logo>
        Require all granted
    </Location>
    <Directory {DEST_DJANGO_ROOT}/demo_logo>
        <Files logo_cpft.png>
            Require all granted
        </Files>
    </Directory>

        # ---------------------------------------------------------------------
        # 3. Restrict to SSL.
        # ---------------------------------------------------------------------
        # a) Enable SSL.
        #    If you haven't already enabled SSL, use:
        #       sudo a2enmod ssl
        #    Somewhere you will need commands like this:
        #          SSLEngine On
        #          SSLCertificateFile /etc/apache2/ssl/www_server_com.crt
        #          SSLCertificateKeyFile /etc/apache2/ssl/server.key
        #          SSLCertificateChainFile /etc/apache2/ssl/www_server_com.ca-bundle
        # b) Restrict CRATE to SSL.
        #    - Set CRATE_HTTPS=True in the CRATE local config file, which sets
        #      several other flags in response to restrict cookies to HTTPS.
        #      (This is the default.)
        #    - Redirect HTTP to HTTPS in Apache. Ensure you have run:
        #       sudo a2enmod rewrite
        #    - Then these commands:

    RewriteEngine On
        #   Don't rewrite for secure connections:
    RewriteCond %{{HTTPS}} off
        #   Send users to HTTPS:
    RewriteRule ^crate/ https://%{{HTTP_HOST}}%{{REQUEST_URI}}

        # ---------------------------------------------------------------------
        # 4. Tell Django where it's living, so it can get its URLs right.
        # ---------------------------------------------------------------------
        # The penultimate piece of the puzzle is to ensure you have this in
        # your CRATE local settings file:
        #       FORCE_SCRIPT_NAME = '/crate'
        # ... which will make Django generate the correct URLs.
        # Note that it will likely confuse and BREAK the Django debugging
        # server (manage.py runserver).
        #
        # ---------------------------------------------------------------------
        # 5. Allow command-line tools to fetch images from the site
        # ---------------------------------------------------------------------
        # And finally... for special PDF generation (so the command-line tool
        # wkhtmltopdf can see the same images as the browser), ensure the local
        # crate settings also includes e.g.:
        #       DJANGO_SITE_ROOT_ABSOLUTE_URL = 'https://mysite.mydomain.com'
        # ... without a trailing slash
        # ... to which the site root (FORCE_SCRIPT_NAME) or the static root
        #     (STATIC_URL), plus the rest of the path, will be appended.
        #
        # ---------------------------------------------------------------------
        # You'll know it's working when all these are OK:
        # ---------------------------------------------------------------------
        #   - browse to http://localhost/crate/
        #   - check a sub-page works
        #   - check the admin sites work and are styled properly
        #   - dev_admin > consent modes > view a traffic-light letter
        #     ... check it works in both HTML (visible to client browsers)
        #         ... if you have a snake-oil SSL certificate, you may have to
        #             set an exemption first
        #     ... and PDF (visible to wkhtmltopdf).
        #         ... wkhtmltopdf won't be bothered by duff SSL certificates.
        #   - check that a clinician e-mail contains correct response URLs to
        #     an absolute machine (that work from a different computer)
        #
        # For debugging, consider:
        # - command-line tools
        #       wget -O - --verbose --no-check-certificate http://127.0.0.1/crate
        # - Apache directives
        #       LogLevel alert rewrite:trace6
        #       LogLevel alert proxy:trace6
        # - remember that browsers cache all sorts of failures and redirects

</VirtualHost>

        """,  # noqa
        file=outfile,
    )

# http://httpd.apache.org/docs/2.2/mod/mod_proxy.html#proxypass
# http://httpd.apache.org/docs/2.2/mod/mod_proxy.html#proxypassreverse
# ... says Unix domain socket (UDS) support came in 2.4.7
# ... but was actually 2.4.9:
#     http://mail-archives.apache.org/mod_mbox/httpd-announce/201403.mbox/%3CF590EEF7-7D4F-4ED7-A810-97ED5AA17DCE@apache.org%3E  # noqa
#     https://httpd.apache.org/docs/trunk/mod/mod_proxy.html#comment_4772
# http://design.canonical.com/2015/08/django-behind-a-proxy-fixing-absolute-urls/

# https://httpd.apache.org/docs/trunk/mod/mod_proxy.html#proxypass
# http://float64.uk/blog/2014/08/20/php-fpm-sockets-apache-mod-proxy-fcgi-ubuntu/

# Upgrading Apache from 2.4.7 to 2.4.9 or 2.4.10 (Ubuntu 14.03.3 LTS,
# # as per lsb_release -a):
# - http://askubuntu.com/questions/539256/how-to-update-apache2-on-ubuntu-14-04-server-to-the-latest-version  # noqa
# - As of 2015-11-24 and Ubuntu 14.03.3 LTS (as per lsb_release -a)
#       apt-cache showpkg apache2  # shows versions
#           ... 2.4.7 is the only available version
#       apt-get install apache2=VERSION  # if possible
# - Similarly, 2.4.7 is the current version for Ubuntu 14.04
#       http://packages.ubuntu.com/trusty/apache2
# - However, we can use this:
#       https://launchpad.net/~ondrej/+archive/ubuntu/apache2?field.series_filter=trusty  # noqa
#       sudo add-apt-repository ppa:ondrej/apache2
#   ... goes to 2.4.17

# =============================================================================
# Copy files
# =============================================================================

# -----------------------------------------------------------------------------
print("Copying Debian files")
# -----------------------------------------------------------------------------
shutil.copy(join(SOURCE_ROOT, "changelog.Debian"), workpath(DEST_DOC_DIR))
subprocess.check_call(
    ["gzip", "-9", workpath(DEST_DOC_DIR, "changelog.Debian")]
)
# ... must be compressed
remove_gzip_timestamp(workpath(DEST_DOC_DIR, "changelog.Debian.gz"))
# ... must not have timestamp

# -----------------------------------------------------------------------------
print("Building Python package")
# -----------------------------------------------------------------------------
# Remove egg info, or files are cached inappropriately.
shutil.rmtree(EGG_DIR, ignore_errors=True)
# setup.py needs to be run from the right directory
os.chdir(SOURCE_ROOT)
subprocess.check_call(
    [PYTHON_WITH_VER, join(SOURCE_ROOT, "setup.py"), "sdist"]
)

# -----------------------------------------------------------------------------
print("Copying package files")
# -----------------------------------------------------------------------------
shutil.copy(
    join(SOURCE_ROOT, "dist", CRATE_PIPFILE), workpath(DEST_CRATE_PIPFILE)
)
remove_gzip_timestamp(workpath(DEST_CRATE_PIPFILE))
# shutil.copy(join(SOURCE_ROOT, 'README.md'), WORK_ROOT)
copy_tree_root(join(SOURCE_ROOT, "tools"), join(WORK_ROOT))
shutil.copy(
    join(
        SOURCE_ROOT,
        PACKAGE_DIR_FROM_SOURCE_ROOT,
        "crateweb",
        "specimen_secret_local_settings",
        LOCAL_CONFIG_BASENAME,
    ),
    workpath(DEST_CRATEWEB_CONF_FILE),
)
shutil.copy(
    workpath(SPECIMEN_SUPERVISOR_CONF_FILE),
    workpath(DEST_SUPERVISOR_CONF_FILE),
)

# =============================================================================
print("Removing junk")
# =============================================================================
subprocess.check_call(
    ["find", WORK_DIR, "-type", "f", "-name", "*.py[co]", "-delete"]
)
subprocess.check_call(
    ["find", WORK_DIR, "-type", "d", "-name", "__pycache__", "-delete"]
)
subprocess.check_call(
    ["find", WORK_DIR, "-type", "f", "-name", ".gitignore", "-delete"]
)

# =============================================================================
print("Setting ownership and permissions")
# =============================================================================
# Make directories executable (or all the subsequent recursions fail).
subprocess.check_call(
    ["find", WORK_DIR, "-type", "d", "-exec", "chmod", "755", "{}", ";"]
)
# Default permissions
subprocess.check_call(
    ["find", WORK_DIR, "-type", "f", "-exec", "chmod", "644", "{}", ";"]
)
# Executables
subprocess.check_call(
    [
        "chmod",
        "a+x",
        # Debian (ignoring any that don't exist)
        join(DEB_DIR, "prerm"),
        join(DEB_DIR, "postrm"),
        join(DEB_DIR, "preinst"),
        join(DEB_DIR, "postinst"),
        # Package
        # --- all done via the "pip install ." equivalent
    ]
)
subprocess.check_call(
    [
        "find",
        WORK_DIR,
        "-type",
        "f",
        "-name",
        "*.sh",
        "-exec",
        "chmod",
        "a+x",
        "{}",
        ";",
    ]
)
# Secrets; requires Lintian non-standard-file-perm
subprocess.check_call(
    [
        "chmod",
        "600",
        workpath(DEST_CRATEWEB_CONF_FILE),
    ]
)

# Ownership: everything is by default owned by root,
# and we change that in the postinst file.

# =============================================================================
print("Building package")
# =============================================================================
subprocess.check_call(
    ["fakeroot", "dpkg-deb", "--build", WORK_DIR, PACKAGENAME]
)
# ... "fakeroot" prefix makes all files installed as root:root

# =============================================================================
print("Checking with Lintian")
# =============================================================================
subprocess.check_call(["lintian", PACKAGENAME])

# =============================================================================
# Clear up temporary workspace
# =============================================================================
if LEAVE_TEMPORARY_WORKSPACE_BEHIND:
    print("DELIBERATELY LEAVING TEMPORARY WORKSPACE: " + WORK_DIR)
else:
    print("Deleting temporary workspace")
    shutil.rmtree(WORK_DIR, ignore_errors=True)  # CAUTION!

# =============================================================================
print("=" * 79)
print("Debian package should be: " + PACKAGENAME)
print("Quick install: sudo gdebi --non-interactive " + DEB_PACKAGE_FILE)
print("Quick remove: sudo apt-get remove " + PACKAGE_FOR_DEB)
# =============================================================================
