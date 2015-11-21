#!/bin/bash

# Adapted from:
#   http://stackoverflow.com/questions/4324558/whats-the-proper-way-to-install-pip-virtualenv-and-distribute-for-python

# Select Python executable:
PYTHON=$(which python3.4)
# Select current version of virtualenv:
VENV_VERSION=13.1.2


warn() {
    # http://stackoverflow.com/questions/5947742/how-to-change-the-output-color-of-echo-in-linux/5947788#5947788
    echo "$(tput setaf 1)$@$(tput sgr0)"
}

require_debian_package() {
    echo "Checking for Debian package: $1"
    dpkg -l $1 >/dev/null && return
    warn "You must install the package $1. On Ubuntu, use the command:"
    warn "    sudo apt-get install $1"
    exit 1
}


# Set the CRATE_VIRTUALENV environment variable from the first argument
# ... minus any trailing slashes
#     http://stackoverflow.com/questions/9018723/what-is-the-simplest-way-to-remove-a-trailing-slash-from-each-parameter
shopt -s extglob
export CRATE_VIRTUALENV="${1%%+(/)}"
if [ "$CRATE_VIRTUALENV" == "" ]; then
    echo "Syntax:"
    echo "    $0 CRATE_VIRTUALENV"
    echo
    echo "Please specify the directory in which the virtual environment should"
    echo "be created. For example:"
    echo
    echo "    $0 ~/crate_virtualenv"
    exit 1
fi

# Exit on any error:
set -e

CRATE_VIRTUALENV=`readlink -m $CRATE_VIRTUALENV`  # removes any trailing /
THIS_SCRIPT_DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
CRATE_BASE=`readlink -m $THIS_SCRIPT_DIR/..`
CRATE_DJANGO_ROOT=$CRATE_BASE/crateweb

PYTHONBASE=`basename $PYTHON`
SITE_PACKAGES="$CRATE_VIRTUALENV/lib/$PYTHONBASE/site-packages"

echo "========================================================================"
echo "1. Prerequisites, from $CRATE_BASE/requirements-ubuntu.txt"
echo "========================================================================"
while read package; do
    require_debian_package $package
done <$CRATE_BASE/requirements-ubuntu.txt

echo "========================================================================"
echo "2. Downloading and installing virtualenv into a temporary space"
echo "========================================================================"
VENV_URL_BASE=https://pypi.python.org/packages/source/v/virtualenv
TEMPDIR=`mktemp -d`
pushd $TEMPDIR
curl -O $VENV_URL_BASE/virtualenv-$VENV_VERSION.tar.gz
# Extract it
tar xzf virtualenv-$VENV_VERSION.tar.gz

echo "========================================================================"
echo "3. Using system Python ($PYTHON) and downloaded virtualenv software to make $CRATE_VIRTUALENV"
echo "========================================================================"
$PYTHON virtualenv-$VENV_VERSION/virtualenv.py $CRATE_VIRTUALENV
# Install virtualenv into the environment.
$CRATE_VIRTUALENV/bin/pip install virtualenv-$VENV_VERSION.tar.gz
popd

echo "========================================================================"
echo "4. Cleanup"
echo "========================================================================"
rm -rf $TEMPDIR

echo "========================================================================"
echo "5. Make virtual environment set PYTHONPATH etc., pointing to us"
echo "========================================================================"
cat << END_HEREDOC >> $CRATE_VIRTUALENV/bin/activate
export OLD_PYTHONPATH="\$PYTHONPATH"
export PYTHONPATH="$CRATE_BASE:$CRATE_BASE/secret_local_settings"  # *** inappropriate for deployment
export OLD_CLASSPATH="\$CLASSPATH"

export CLASSPATH="/usr/share/java/mysql.jar:$CRATE_BASE/sqljdbc_4.1/enu/sqljdbc41.jar"

export OLD_PATH="\$PATH"
export PATH="$CRATE_DJANGO_ROOT:$CRATE_BASE/tools:\$PATH"
END_HEREDOC

cat << END_HEREDOC >> $CRATE_VIRTUALENV/bin/postdeactivate
export PYTHONPATH="\$OLD_PYTHONPATH"
export CLASSPATH="\$OLD_CLASSPATH"
export PATH="\$OLD_PATH"
END_HEREDOC

echo "========================================================================"
echo "6. Activate our virtual environment, $CRATE_VIRTUALENV"
echo "========================================================================"
source $CRATE_VIRTUALENV/bin/activate
# ... now "python", "pip", etc. refer to the virtual environment
echo "python is now: `which python`"
python --version
echo "pip is now: `which pip`"
pip --version

echo "========================================================================"
echo "7. Install dependencies"
echo "========================================================================"
pip install -r $CRATE_BASE/requirements.txt

# =============================================================================
# Usage
# =============================================================================
export CRATE_MANAGE="$CRATE_DJANGO_ROOT/manage.py"
echo "hello"
cat << END_HEREDOC
===============================================================================
USAGE
===============================================================================
-------------------------------------------------------------------------------
To use Apache with mod_wsgi
-------------------------------------------------------------------------------
(a) Add Ubuntu prerequisites

    sudo apt-get install apache2 libapache2-mod-wsgi-py3 libapache2-mod-xsendfile

(b) Configure Apache for CRATE.
    Use a section like this in the Apache config file (example with 5
    processes):

<VirtualHost *:80>
    # ...

*** reshuffle/sort this bit

    # =========================================================================
    # CRATE
    # =========================================================================

    WSGIDaemonProcess SOME_NAME processes=5 threads=1 python-path=$SITE_PACKAGES:$CRATE_DJANGO_ROOT:PATH/TO/MY/SECRET/CRATE_LOCAL_SETTINGS.PY/DIRECTORY
    WSGIScriptAlias /MY/MOUNT/URL/ $CRATE_DJANGO_ROOT/config/wsgi.py process-group=SOME_NAME application-group=%{GLOBAL}

    Alias /MY/MOUNT/URL/static/admin/ $SITE_PACKAGES/django/contrib/admin/static/admin/
    Alias /MY/MOUNT/URL/static/ $CRATE_DJANGO_ROOT/static/

    <Directory $CRATE_DJANGO_ROOT/config>
        <Files "wsgi.py">
            Require all granted
        </Files>
    </Directory

</VirtualHost>

(c) Additionally, install mod_xsendfile, e.g. (on Ubuntu):

        sudo apt-get install libapache2-mod-xsendfile

    ... which will implicitly run "a2enmod xsendfile" to enable it. Then add to
    the Apache config file in an appropriate place:

        <IfModule mod_xsendfile.c>
            XSendFile on
            XSendFilePath /MY/SECRET/CRATE/FILE/ZONE
            # ... as configured in your secret crate_local_settings.py
        </IfModule>

- If you get problems, check the log, typically /var/log/apache2/error.log
- If it's a permissions problem, check the www-data user can see the file:
    sudo -u www-data cat FILE
    # ... using an absolute path
    groups USER
- If Chrome fails to load GIFs and says "pending" in the Network developer
  view, restart Chrome. (Probably only a "caching of failure" during
  development!)

-------------------------------------------------------------------------------
With mod_wsgi-express
-------------------------------------------------------------------------------

    pip install mod_wsgi-httpd  # a bit slow; don't worry
    pip install mod_wsgi

    mod_wsgi-express start-server config.wsgi \\
        --application-type module \\
        --log-to-terminal \\
        --port 80 \\
        --processes 5 \\
        --python-path PATH/TO/MY/SECRET/CRATE_LOCAL_SETTINGS.PY/DIRECTORY \\
        --threads 1 \\
        --url-alias /static $CRATE_DJANGO_ROOT/static \\
        --working-directory $CRATE_DJANGO_ROOT

- This changes to the working directory and uses config/wsgi.py
- Add --reload-on-changes for debugging.
- Port 80 will require root privilege.

-------------------------------------------------------------------------------
Command-line use
-------------------------------------------------------------------------------
For convenience:

    export \$CRATE_VIRTUALENV="$CRATE_VIRTUALENV"
    export \$CRATE_MANAGE="$CRATE_MANAGE"

To activate virtual environment:
    source \$CRATE_VIRTUALENV/bin/activate

Then use \$CRATE_MANAGE as the Django management tool, e.g. for the demo server:
    \$CRATE_MANAGE runserver
END_HEREDOC
TESTING_VAR=$(cat <<'END_HEREDOC'

###############################################################################

    # Define a process group
    WSGIDaemonProcess crate_pg processes=5 threads=1 python-path=/home/rudolf/crate_virtualenv/lib/python3.4/site-packages:/home/rudolf/Documents/code/crate/crateweb:/home/rudolf/Documents/code/crate/secret_local_settings

    # Point a particular URL to a particular WSGI script
    WSGIScriptAlias /crate /home/rudolf/Documents/code/crate/crateweb/config/wsgi.py

    # Redirect requests for static files, and admin static files.
    # MIND THE ORDER - more specific before less specific.
    Alias /static/admin/ /home/rudolf/crate_virtualenv/lib/python3.4/site-packages/django/contrib/admin/static/admin/
    Alias /static/debug_toolbar/ /home/rudolf/crate_virtualenv/lib/python3.4/site-packages/debug_toolbar/static/debug_toolbar/
    Alias /static/ /home/rudolf/Documents/code/crate/crateweb/static/

    # Make our set of processes use a specific process group
    <Location /crate>
        WSGIProcessGroup crate_pg
    </Location>

    # Allow access to the WSGI script
    <Directory /home/rudolf/Documents/code/crate/crateweb/config>
        <Files "wsgi.py">
            Require all granted
        </Files>
    </Directory>

    # Allow access to the static files
    <Directory /home/rudolf/Documents/code/crate/crateweb/static>
        Require all granted
    </Directory>

    # Allow access to the admin static files
    <Directory /home/rudolf/crate_virtualenv/lib/python3.4/site-packages/django/contrib/admin/static/admin>
        Require all granted
    </Directory>

    # Allow access to the debug toolbar static files
    <Directory /home/rudolf/crate_virtualenv/lib/python3.4/site-packages/debug_toolbar/static/debug_toolbar>
        Require all granted
    </Directory>

    # Turn on XSendFile
    <IfModule mod_xsendfile.c>
        XSendFile on
        XSendFilePath /home/rudolf/Documents/code/crate/working/crateweb/crate_filestorage
    </IfModule>

###############################################################################

mod_wsgi-express start-server config.wsgi \
    --access-log \
    --startup-log \
    --application-type module \
    --log-to-terminal \
    --port 8000 \
    --processes 5 \
    --python-path ~/Documents/code/crate/secret_local_settings \
    --reload-on-changes \
    --threads 1 \
    --url-alias /static ~/Documents/code/crate/crateweb/static \
    --working-directory ~/Documents/code/crate/crateweb

###############################################################################

END_HEREDOC
)

# http://blog.dscpl.com.au/2015/04/introducing-modwsgi-express.html
# http://blog.dscpl.com.au/2015/04/using-modwsgi-express-with-django.html
# http://blog.dscpl.com.au/2015/04/integrating-modwsgi-express-as-django.html
# http://blog.dscpl.com.au/2015/05/using-modwsgi-express-as-development.html
# https://pypi.python.org/pypi/mod_wsgi
# https://gist.github.com/GrahamDumpleton/b79d336569054882679e

# https://opensourcemissions.wordpress.com/2010/03/12/finally-a-working-django-non-root-url-with-mod_wsgi/
# https://groups.google.com/forum/#!topic/django-users/xFdZnKq26H0
# https://code.djangoproject.com/ticket/8906

# http://stackoverflow.com/questions/30566836/how-to-autostart-apachectl-script-that-mod-wsgi-express-made-for-django
