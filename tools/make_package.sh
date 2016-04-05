#!/bin/bash
# -xv

# Exit on any error
set -e

#==============================================================================
# Functions
#==============================================================================

error() {
    # http://stackoverflow.com/questions/5947742/how-to-change-the-output-color-of-echo-in-linux/5947788#5947788
    echo "$(tput setaf 1)$(tput bold)$@$(tput sgr0)"  # red
    # 1 red, 2 green, 3 ?dark yellow, 4 blue, 5 magenta, 6 cyan, 7 white
}

warn() {
    echo "$(tput setaf 3)$(tput bold)$@$(tput sgr0)"  # yellow
}

reassure() {
    echo "$(tput setaf 2)$(tput bold)$@$(tput sgr0)"  # green
}

bold() {
    echo "$(tput bold)$@$(tput sgr0)"
}

command_exists() {
    # returns 0 (true) for found, 1 (false) for not found
    if command -v $1 >/dev/null; then
        return 0  # found
    else
        return 1  # not found
    fi
}

fail() {
    error "$1"
    exit 1
}

require_command() {
    command_exists "$1" || {
        fail "$1 command not found; stopping"
    }
}

require_debian_package() {
    echo "Checking for Debian package: $1"
    dpkg -l $1 >/dev/null && return
    warn "You must install the package $1. On Ubuntu, use the command:"
    warn "    sudo apt-get install $1"
    exit 1
}

user_is_root() {
    if [[ $EUID -eq 0 ]]; then
        return 0  # root
    else
        return 1  # not root
    fi
}

require_root() {
    user_is_root || {
        fail "This script must be run using sudo or as the root user"
    }
}

require_not_root() {
    # Do not use: user_is_root && fail "blahblah"
    # ... because we're using "set -e", so it'll exit silently otherwise.
    ! user_is_root || {
        fail "This script should not be run using sudo or as the root user"
    }
}

#==============================================================================
# Variables
#==============================================================================

#------------------------------------------------------------------------------
# Package
#------------------------------------------------------------------------------

PACKAGE=crate

#------------------------------------------------------------------------------
# User and other default config
#------------------------------------------------------------------------------

CRATE_USER=www-data
CRATE_GROUP=www-data

MAKE_USER=false  # not working properly yet
MAKE_GROUP=false

DEFAULT_GUNICORN_PORT=8005
DEFAULT_GUNICORN_SOCKET=/tmp/.crate_gunicorn.sock  # must be writable by CRATE_USER
# http://unix.stackexchange.com/questions/88083/idiomatic-location-for-file-based-sockets-on-debian-systems

#------------------------------------------------------------------------------
# Directories
#------------------------------------------------------------------------------

# Source
THIS_SCRIPT_DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
SOURCE_ROOT=`readlink -m "$THIS_SCRIPT_DIR/.."`
PACKAGE_DIR="$SOURCE_ROOT/built_packages"

# Destination, as seen on the final system
DEST_ROOT=/usr/share/$PACKAGE
DEST_DJANGO_ROOT=$DEST_ROOT/crateweb
# ... Lintian dislikes files/subdirectories in: /usr/bin/X, /usr/local/X, /opt/X
# ... It dislikes images in /usr/lib
DEST_VIRTUALENV=$DEST_ROOT/virtualenv
DEST_SITE_PACKAGES=
DEST_PACKAGE_CONF_DIR=/etc/$PACKAGE
DEST_SUPERVISOR_CONF_DIR=/etc/supervisor/conf.d
INFO_DEST_DPKG_DIR=/var/lib/dpkg/info  # not written to directly
DEST_DOC_DIR=/usr/share/doc/$PACKAGE
DEST_COLLECTED_STATIC_DIR=$DEST_DJANGO_ROOT/static_collected

# Working/Debian
WORK_DIR=/tmp/crate_debian_pkg_build_tmp
# Prefix WORK_DIR to other things, e.g. $WORK_DIR$DEST_ROOT, for the intermediate location.
DEB_DIR=$WORK_DIR/DEBIAN  # where Debian package control information lives
DEB_OVERRIDE_DIR=$WORK_DIR/usr/share/lintian/overrides

#------------------------------------------------------------------------------
# Software
#------------------------------------------------------------------------------

VERSION_MAIN=$(head -n 1 "$SOURCE_ROOT/VERSION.txt")
VERSION_DEB="${VERSION_MAIN}-1"
PYTHONBASE="python3.4"

#------------------------------------------------------------------------------
# Files
#------------------------------------------------------------------------------

SPECIMEN_SUPERVISOR_CONF_FILE=$DEST_ROOT/specimen_etc_supervisor_conf.d_crate.conf
DEST_SUPERVISOR_CONF_FILE=$DEST_SUPERVISOR_CONF_DIR/$PACKAGE.conf
DEB_PACKAGE_FILE=$PACKAGE_DIR/${PACKAGE}_${VERSION_DEB}_all.deb
LOCAL_CONFIG_BASENAME="crate_local_settings.py"
DEST_CRATE_CONF_FILE=$DEST_PACKAGE_CONF_DIR/$LOCAL_CONFIG_BASENAME
INSTRUCTIONS=$DEST_ROOT/instructions.txt

#------------------------------------------------------------------------------
# Dependencies
#------------------------------------------------------------------------------

mapfile -t DEPENDS_DEB_ARRAY < "$SOURCE_ROOT/requirements-ubuntu.txt"
if [ "$MAKE_GROUP" = true ] || [ "$MAKE_USER" = true ]; then
    DEPENDS_DEB_ARRAY+=('adduser')
fi

SAVE_IFS=$IFS
IFS=","
DEPENDS_DEB="${DEPENDS_DEB_ARRAY[*]}"  # comma-separated list
IFS=$SAVE_IFS

#==============================================================================
# Prerequisites; directories
#==============================================================================

reassure "Building .deb package for $PACKAGE version $VERSION_MAIN"

#------------------------------------------------------------------------------
# Prerequisites
#------------------------------------------------------------------------------
bold "=== Checking prerequisites"
require_not_root
require_command dpkg-deb
reassure "OK"

#------------------------------------------------------------------------------
# Make directories
#------------------------------------------------------------------------------
bold "=== Making directories"
cd /  # ... just in case we're called from a nonexisting (removed) directory
if [ -d "$WORK_DIR" ]; then
  fail "Working directory $WORK_DIR already exists"
fi
mkdir -p $WORK_DIR
mkdir -p $WORK_DIR$DEST_ROOT
mkdir -p $WORK_DIR$DEST_PACKAGE_CONF_DIR
mkdir -p $WORK_DIR$DEST_SUPERVISOR_CONF_DIR
mkdir -p $WORK_DIR$DEST_DOC_DIR
mkdir -p $DEB_DIR
mkdir -p $DEB_OVERRIDE_DIR
reassure "OK"

#==============================================================================
# Debian files
#==============================================================================

bold "=== Creating Debian package files"

#------------------------------------------------------------------------------
# Debian package file: preinst
#------------------------------------------------------------------------------
echo "Creating Debian preinst file. Will be installed as $INFO_DEST_DPKG_DIR/$PACKAGE.preinst"
# for heredocs, quoting the limit string prevents variable interpretation
cat << END_HEREDOC > $DEB_DIR/preinst
#!/bin/bash
set -e  # Exit on any errors. (Lintian strongly advises this.)

echo "Stop services that may be affected"
service supervisor stop
END_HEREDOC

#------------------------------------------------------------------------------
# Debian package file: postinst
#------------------------------------------------------------------------------
echo "Creating Debian postinst file. Will be installed as $INFO_DEST_DPKG_DIR/$PACKAGE.postinst"
# for heredocs, quoting the limit string prevents variable interpretation
if [ "$MAKE_GROUP" = true ] ; then
    MAKE_GROUP_COMMAND_1="echo '=== Adding group $CRATE_GROUP'"
    # MAKE_GROUP_COMMAND_2="addgroup --system $CRATE_GROUP"
    MAKE_GROUP_COMMAND_2="addgroup $CRATE_GROUP"
else
    MAKE_GROUP_COMMAND_1="# No need to add user"
    MAKE_GROUP_COMMAND_2=""
fi
if [ "$MAKE_USER" = true ] ; then
    MAKE_USER_COMMAND_1="echo '=== Adding system user $CRATE_USER in group $CRATE_GROUP'"
    # MAKE_USER_COMMAND_2="adduser --system --ingroup $CRATE_GROUP --home /home/$CRATE_USER $CRATE_USER"
    MAKE_USER_COMMAND_2="adduser --system --ingroup $CRATE_GROUP $CRATE_USER"
    # MAKE_USER_COMMAND_2="adduser --ingroup $CRATE_GROUP $CRATE_USER"
    # https://lintian.debian.org/tags/maintainer-script-should-not-use-adduser-system-without-home.html
    # http://unix.stackexchange.com/questions/47880/how-debian-package-should-create-user-accounts
else
    MAKE_USER_COMMAND_1="# No need to add user"
    MAKE_USER_COMMAND_2=""
fi
cat << END_HEREDOC > $DEB_DIR/postinst
#!/bin/bash
set -e  # Exit on any errors. (Lintian strongly advises this.)

bold() {
    echo "\$(tput bold)\$@\$(tput sgr0)"
}

echo '$PACKAGE: postinst file executing'

$MAKE_GROUP_COMMAND_1
$MAKE_GROUP_COMMAND_2
$MAKE_USER_COMMAND_1
$MAKE_USER_COMMAND_2

echo "Setting ownership"
chown -R $CRATE_USER:$CRATE_GROUP $DEST_ROOT
chown $CRATE_USER:$CRATE_GROUP $DEST_SUPERVISOR_CONF_FILE
chown $CRATE_USER:$CRATE_GROUP $DEST_CRATE_CONF_FILE

echo "Installing virtual environment..."
# Note the need to set XDG_CACHE_HOME, or pip will use the wrong user's
# $HOME variable.
sudo --user=$CRATE_USER XDG_CACHE_HOME=$DEST_ROOT/.cache python3 "$DEST_ROOT/tools/install_virtualenv.py" "$DEST_VIRTUALENV"
echo "... finished installing virtual environment"

echo "Collecting static files"
source $DEST_VIRTUALENV/bin/activate
# Run temporarily without local settings file (since the default raises an exception):
export CRATE_RUN_WITHOUT_LOCAL_SETTINGS=yes
manage.py collectstatic --noinput
deactivate

echo "Restart services that may have been affected"
service supervisor restart

echo '$PACKAGE: postinst file finished'

echo
bold "Please read this file: $INSTRUCTIONS"
echo

END_HEREDOC

#------------------------------------------------------------------------------
# Debian package file: prerm
#------------------------------------------------------------------------------
#echo "Creating Debian prerm file. Will be installed as $INFO_DEST_DPKG_DIR/$PACKAGE.prerm"
## for heredocs, quoting the limit string prevents variable interpretation
cat << END_HEREDOC > $DEB_DIR/prerm
#!/bin/bash
set -e  # Exit on any errors. (Lintian strongly advises this.)

echo "Stop services that may be affected"
service supervisor stop

echo "Remove virtual environment"
rm -rf "$DEST_VIRTUALENV"
END_HEREDOC

#------------------------------------------------------------------------------
# Debian package file: postrm
#------------------------------------------------------------------------------
echo "Creating Debian postrm file. Will be installed as $INFO_DEST_DPKG_DIR/$PACKAGE.postrm"
# for heredocs, quoting the limit string prevents variable interpretation
cat << END_HEREDOC > $DEB_DIR/postrm
#!/bin/bash
set -e  # Exit on any errors. (Lintian strongly advises this.)

echo "Restart services that may be affected"
service supervisor restart
END_HEREDOC

#------------------------------------------------------------------------------
# Debian package file: control
#------------------------------------------------------------------------------
echo "Creating Debian control file"
cat << END_HEREDOC > $DEB_DIR/control
Package: $PACKAGE
Version: $VERSION_DEB
Section: science
Priority: optional
Architecture: all
Maintainer: Rudolf Cardinal <rudolf@pobox.com>
Depends: $DEPENDS_DEB
Description: Clinical Records Anonymisation and Text Extraction (CRATE).
 CRATE allows you to do the following:
 (1) Anonymise a relational database.
 (2) Run external natural language processing (NLP) tools over a database.
 (3) Provide a research web front end.
 (4) Manage a consent-to-contact framework that's anonymous to researchers.
END_HEREDOC

#------------------------------------------------------------------------------
# Debian package file: conffiles
#------------------------------------------------------------------------------
# List of configuration files that we're installing.
echo "Creating Debian conffiles file. Will be installed as $INFO_DEST_DPKG_DIR/$PACKAGE.conffiles"
cat << END_HEREDOC > $DEB_DIR/conffiles
$DEST_CRATE_CONF_FILE
$DEST_SUPERVISOR_CONF_FILE
END_HEREDOC
# If a configuration file is removed by the user, it won't be reinstalled:
#       http://www.debian.org/doc/debian-policy/ap-pkg-conffiles.html
# In this situation, do "sudo aptitude purge crate" then reinstall.

#------------------------------------------------------------------------------
# Debian package file: copyright
#------------------------------------------------------------------------------
echo "Creating Debian copyright file. Will be installed as $DEST_DOC_DIR/copyright"
cat << END_HEREDOC > $WORK_DIR$DEST_DOC_DIR/copyright
$PACKAGE

CRATE

    Copyright (C) 2015-2015 Rudolf Cardinal (rudolf@pobox.com).
    Department of Psychiatry, University of Cambridge.

    Licensed under the Apache License, Version 2.0 (the 'License');
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an 'AS IS' BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

ADDITIONAL LIBRARY COMPONENTS

    Public domain or copyright (C) their respective authors (for details,
    see attribution in the source code and other license terms packaged with
    the source).

END_HEREDOC

#------------------------------------------------------------------------------
# Debian/Lintian file: override
#------------------------------------------------------------------------------
echo "Creating Lintian override file"
cat << END_HEREDOC > $DEB_OVERRIDE_DIR/$PACKAGE
# Not an official new Debian package, so ignore this one.
# If we did want to close a new-package ITP bug: http://www.debian.org/doc/manuals/developers-reference/pkgs.html#upload-bugfix
$PACKAGE binary: new-package-should-close-itp-bug
$PACKAGE binary: extra-license-file
$PACKAGE binary: embedded-javascript-library
END_HEREDOC

reassure "OK"

#==============================================================================
# Destination files
#==============================================================================

bold "=== Creating destination files"

# Don't use a gunicorn_start script like this one:
#   http://michal.karzynski.pl/blog/2013/06/09/django-nginx-gunicorn-virtualenv-supervisor/
# ... it doesn't work (supervisord doesn't stop it properly)
# Just use the supervisor conf file.

#------------------------------------------------------------------------------
# Destination file: /etc/supervisor/conf.d/crate.conf
#------------------------------------------------------------------------------
echo "Creating: $DEST_SUPERVISOR_CONF_FILE and $SPECIMEN_SUPERVISOR_CONF_FILE"
cat << END_HEREDOC > "$WORK_DIR$SPECIMEN_SUPERVISOR_CONF_FILE"

; IF YOU EDIT THIS FILE, run:
;       sudo service supervisor restart
; TO MONITOR SUPERVISOR, run:
;       sudo service supervisorctl status
; NOTES:
; - You can't put quotes around the directory variable
;   http://stackoverflow.com/questions/10653590
; - Programs like celery and gunicorn that are installed within a virtual
;   environment use the virtualenv's python via their shebang.

[program:crate-celery-worker]

command = $DEST_VIRTUALENV/bin/celery worker --app=consent --loglevel=info
directory = $DEST_DJANGO_ROOT
environment = PYTHONPATH="$DEST_ROOT",CRATE_LOCAL_SETTINGS="$DEST_CRATE_CONF_FILE"
user = $CRATE_USER
stdout_logfile = /var/log/supervisor/${PACKAGE}_celery.log
stderr_logfile = /var/log/supervisor/${PACKAGE}_celery_err.log
autostart = true
autorestart = true
startsecs = 10
stopwaitsecs = 600

[program:crate-gunicorn]

command = $DEST_VIRTUALENV/bin/gunicorn config.wsgi:application --workers 4 --bind=unix:$DEFAULT_GUNICORN_SOCKET
; Alternative methods (port and socket respectively):
;   --bind=127.0.0.1:$DEFAULT_GUNICORN_PORT
;   --bind=unix:$DEFAULT_GUNICORN_SOCKET
directory = $DEST_DJANGO_ROOT
environment = PYTHONPATH="$DEST_ROOT",CRATE_LOCAL_SETTINGS="$DEST_CRATE_CONF_FILE"
user = $CRATE_USER
stdout_logfile = /var/log/supervisor/${PACKAGE}_gunicorn.log
stderr_logfile = /var/log/supervisor/${PACKAGE}_gunicorn_err.log
autostart = true
autorestart = true
startsecs = 10
stopwaitsecs = 60

END_HEREDOC

#------------------------------------------------------------------------------
# Destination file: instructions.txt
#------------------------------------------------------------------------------
echo "Creating: $INSTRUCTIONS"
SITE_PACKAGES=$DEST_VIRTUALENV/lib/$PYTHONBASE/site-packages
CRATE_MANAGE=$DEST_DJANGO_ROOT/manage.py
cat << END_HEREDOC > "$WORK_DIR$INSTRUCTIONS"
===============================================================================
Your system's CRATE configuration
===============================================================================
- Default CRATE config is:
    $DEST_CRATE_CONF_FILE"
  This must be edited before it will run properly.

- Gunicorn/Celery are being supervised as per:
    $DEST_SUPERVISOR_CONF_FILE
  This this should be edited to point to the correct CRATE config.
  (And copied, in the unlikely event you should want to run >1 instance.)

- Gunicorn default port is:
    $DEFAULT_GUNICORN_PORT
  To change this, edit
    $DEST_SUPERVISOR_CONF_FILE
  Copy this script to run another instance on another port.

- Static file root to serve:
    $DEST_COLLECTED_STATIC_DIR
  See instructions below re Apache.

===============================================================================
Command-line use: Django development server
===============================================================================
For convenience:

    export \$CRATE_VIRTUALENV="$DEST_VIRTUALENV"
    export \$CRATE_MANAGE="$CRATE_MANAGE"

To activate virtual environment:
    source \$CRATE_VIRTUALENV/bin/activate

Then use \$CRATE_MANAGE as the Django management tool.
Once you've activated the virtual environment, you can do this for a demo
server:
    manage.py runserver

Its default port will be 8000.

To deactivate the virtual environment:
    deactivate

===============================================================================
Full stack
===============================================================================

- Gunicorn serves CRATE via WSGI
  ... serving via an internal port (in the default configuration, $DEFAULT_GUNICORN_PORT).

- Celery talks to CRATE (in the web "foreground" and in the background)

- RabbitMQ handles messaging for Celery

- supervisord keeps Gunicorn and Celery running

- You should use a proper web server like Apache or nginx to:

    (a) serve static files
        ... offer URL: <your_crate_app_path>/static
        ... from filesystem: $DEST_COLLECTED_STATIC_DIR

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
        #    ... either via port $DEFAULT_GUNICORN_PORT
        #    ... or, better, via socket $DEFAULT_GUNICORN_SOCKET
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
    # ProxyPass /crate https://127.0.0.1:$DEFAULT_GUNICORN_PORT
    # ProxyPassReverse /crate https://127.0.0.1:$DEFAULT_GUNICORN_PORT
        # Socket (Apache 2.4.9 and higher)
    ProxyPass /crate unix:$DEFAULT_GUNICORN_SOCKET|https://localhost
    ProxyPassReverse /crate unix:$DEFAULT_GUNICORN_SOCKET|https://localhost
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

    Alias /crate_static/ $DEST_COLLECTED_STATIC_DIR/
    <Directory $DEST_COLLECTED_STATIC_DIR>
        Require all granted
    </Directory>

        # If you want your logo to be visible in the dev_admin test view,
        # then make this enable access to the URL you specified as
        # PDF_LOGO_ABS_URL in the config:

    Alias /crate_logo /usr/share/crate/crateweb/static/demo_logo/logo_cpft.png
    <Location /crate_logo>
        Require all granted
    </Location>
    <Directory /usr/share/crate/crateweb/demo_logo>
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
        #    - Redirect HTTP to HTTPS in Apache. Ensure you have run:
        #       sudo a2enmod rewrite
        #    - Then these commands:

    RewriteEngine On
        #   Don't rewrite for secure connections:
    RewriteCond %{HTTPS} off
        #   Send users to HTTPS:
    RewriteRule ^crate/ https://%{HTTP_HOST}%{REQUEST_URI}

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

END_HEREDOC

# http://httpd.apache.org/docs/2.2/mod/mod_proxy.html#proxypass
# http://httpd.apache.org/docs/2.2/mod/mod_proxy.html#proxypassreverse
# ... says Unix domain socket (UDS) support came in 2.4.7
# ... but was actually 2.4.9:
#     http://mail-archives.apache.org/mod_mbox/httpd-announce/201403.mbox/%3CF590EEF7-7D4F-4ED7-A810-97ED5AA17DCE@apache.org%3E
#     https://httpd.apache.org/docs/trunk/mod/mod_proxy.html#comment_4772
# http://design.canonical.com/2015/08/django-behind-a-proxy-fixing-absolute-urls/

# https://httpd.apache.org/docs/trunk/mod/mod_proxy.html#proxypass
# http://float64.uk/blog/2014/08/20/php-fpm-sockets-apache-mod-proxy-fcgi-ubuntu/

# Upgrading Apache from 2.4.7 to 2.4.9 or 2.4.10 (Ubuntu 14.03.3 LTS, as per lsb_release -a):
# - http://askubuntu.com/questions/539256/how-to-update-apache2-on-ubuntu-14-04-server-to-the-latest-version
# - As of 2015-11-24 and Ubuntu 14.03.3 LTS (as per lsb_release -a)
#       apt-cache showpkg apache2  # shows versions
#           ... 2.4.7 is the only available version
#       apt-get install apache2=VERSION  # if possible
# - Similarly, 2.4.7 is the current version for Ubuntu 14.04
#       http://packages.ubuntu.com/trusty/apache2
# - However, we can use this:
#       https://launchpad.net/~ondrej/+archive/ubuntu/apache2?field.series_filter=trusty
#       sudo add-apt-repository ppa:ondrej/apache2
#   ... goes to 2.4.17

reassure "OK"

#==============================================================================
# Copy; ownership/permissions; build; clean up
#==============================================================================

#------------------------------------------------------------------------------
# Copy/set permissions
#------------------------------------------------------------------------------
bold "=== Copying and setting ownership/permissions"

echo "Copying Debian files"
cp $SOURCE_ROOT/changelog.Debian $WORK_DIR$DEST_DOC_DIR
gzip -9 $WORK_DIR$DEST_DOC_DIR/changelog.Debian  # must be compressed

echo "Copying package files"
cp -R $SOURCE_ROOT/anonymise $WORK_DIR$DEST_ROOT
cp -R $SOURCE_ROOT/bug_reports $WORK_DIR$DEST_ROOT
cp -R $SOURCE_ROOT/crateweb $WORK_DIR$DEST_ROOT
cp -R $SOURCE_ROOT/docs $WORK_DIR$DEST_ROOT
cp -R $SOURCE_ROOT/mysql_auditor $WORK_DIR$DEST_ROOT
cp -R $SOURCE_ROOT/pythonlib $WORK_DIR$DEST_ROOT
cp -R $SOURCE_ROOT/nlp_manager $WORK_DIR$DEST_ROOT
cp -R $SOURCE_ROOT/tools $WORK_DIR$DEST_ROOT
cp -R $SOURCE_ROOT/*.md $WORK_DIR$DEST_ROOT
cp -R $SOURCE_ROOT/*.txt $WORK_DIR$DEST_ROOT

cp $SOURCE_ROOT/crateweb/specimen_secret_local_settings/$LOCAL_CONFIG_BASENAME $WORK_DIR$DEST_CRATE_CONF_FILE
cp $WORK_DIR$SPECIMEN_SUPERVISOR_CONF_FILE $WORK_DIR$DEST_SUPERVISOR_CONF_FILE

echo "Remove rubbish"
find $WORK_DIR -type f -name "*.py[co]" -delete
find $WORK_DIR -type d -name "__pycache__" -delete
find $WORK_DIR -type f -name ".gitignore" -delete

echo "Set permissions"
# Global
# Make directories executable (or all the subsequent recursions fail).
find $WORK_DIR -type d -exec chmod 755 {} \;
find $WORK_DIR -type f -exec chmod 644 {} \;
# Debian (ignoring any that don't exist)
chmod a+x $DEB_DIR/preinst --quiet || :
chmod a+x $DEB_DIR/postinst --quiet || :
chmod a+x $DEB_DIR/prerm --quiet || :
chmod a+x $DEB_DIR/postrm --quiet || :
# Package
chmod a+x $WORK_DIR$DEST_ROOT/anonymise/anonymise.py
chmod a+x $WORK_DIR$DEST_ROOT/anonymise/test_anonymisation.py
chmod a+x $WORK_DIR$DEST_ROOT/nlp_manager/nlp_manager.py
chmod a+x $WORK_DIR$DEST_ROOT/crateweb/manage.py
find $WORK_DIR$DEST_ROOT -iname "*.sh" -exec chmod a+x {} \;
# Extras
#chmod a+x $WORK_DIR$DEST_ROOT/gunicorn_start

# Ownership: everything is by default owned by root,
# and we change that in the postinst file.

reassure "OK"

#------------------------------------------------------------------------------
# Build package, check
#------------------------------------------------------------------------------
bold "=== Building package"
fakeroot dpkg-deb --build $WORK_DIR $DEB_PACKAGE_FILE
# ... "fakeroot" prefix makes all files installed as root:root
reassure "OK"

bold "=== Checking with Lintian"
lintian $DEB_PACKAGE_FILE
reassure "OK"

reassure "Debian package is: $DEB_PACKAGE_FILE"
reassure "Quick install: sudo gdebi --non-interactive $DEB_PACKAGE_FILE"
reassure "Quick remove: sudo apt-get remove $PACKAGE"

#------------------------------------------------------------------------------
# Cleaning up
#------------------------------------------------------------------------------
bold "=== Cleaning up"
rm -rf "$WORK_DIR"

#==============================================================================
# Done
#==============================================================================
reassure "OK"
exit 0
