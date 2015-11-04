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

THIS_SCRIPT_DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )

echo "========================================================================"
echo "1. Prerequisites"
echo "========================================================================"
require_debian_package python3-dev

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
echo "5. Activate our virtual environment, $CRATE_VIRTUALENV"
echo "========================================================================"
source $CRATE_VIRTUALENV/bin/activate
# ... now "python", "pip", etc. refer to the virtual environment
echo "python is now: `which python`"
python --version
echo "pip is now: `which pip`"
pip --version

echo "========================================================================"
echo "6. Install dependencies"
echo "========================================================================"
pip install -r $THIS_SCRIPT_DIR/../requirements.txt

echo "========================================================================"
echo "USAGE:"
echo "========================================================================"
PYTHONBASE=`basename $PYTHON`
echo "To activate virtual environment:"
echo "    source $CRATE_VIRTUALENV/bin/activate"
echo "To use Apache/mod_wsgi, this goes in the Apache config file:"
echo "    WSGIDaemonProcess NAME [OTHER_OPTIONS] python-path=$CRATE_VIRTUALENV/lib/$PYTHONBASE/site-packages"
echo "Setting \$CRATE_VIRTUALENV to $CRATE_VIRTUALENV"
echo "Use the SET_PATHS.sh tool for subsequent convenient path-setting."
