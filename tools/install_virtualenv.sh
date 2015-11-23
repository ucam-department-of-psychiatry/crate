#!/bin/bash

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

require_debian_package() {
    echo "Checking for Debian package: $1"
    dpkg -l $1 >/dev/null && return
    warn "You must install the package $1. On Ubuntu, use the command:"
    warn "    sudo apt-get install $1"
    exit 1
}

#==============================================================================
# Parameters
#==============================================================================

# Set the CRATE_VIRTUALENV environment variable from the first argument
# ... minus any trailing slashes
#     http://stackoverflow.com/questions/9018723/what-is-the-simplest-way-to-remove-a-trailing-slash-from-each-parameter
shopt -s extglob
export CRATE_VIRTUALENV="${1%%+(/)}"

if [ "$CRATE_VIRTUALENV" == "" ]; then
    error "Invalid parameters"
    cat << END_HEREDOC
Syntax:
    $0 CRATE_VIRTUALENV

Please specify the directory in which the virtual environment should be
created. For example, for a testing environment
    $0 ~/crate_virtualenv

or for a production environment:
    sudo --user=www-data XDG_CACHE_HOME=/usr/share/crate/.cache $0 /usr/share/crate/virtualenv

END_HEREDOC
    exit 1
fi

#==============================================================================
# Variables
#==============================================================================

#------------------------------------------------------------------------------
# Software
#------------------------------------------------------------------------------
# Select Python executable:
PYTHON=$(which python3.4)
# Select current version of virtualenv:
VENV_VERSION=13.1.2

#------------------------------------------------------------------------------
# Directories
#------------------------------------------------------------------------------
CRATE_VIRTUALENV=`readlink -m $CRATE_VIRTUALENV`  # removes any trailing /
THIS_SCRIPT_DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
CRATE_BASE=`readlink -m "$THIS_SCRIPT_DIR/.."`
CRATE_DJANGO_ROOT="$CRATE_BASE/crateweb"

PYTHONBASE=`basename $PYTHON`
SITE_PACKAGES="$CRATE_VIRTUALENV/lib/$PYTHONBASE/site-packages"

#==============================================================================
# Main
#==============================================================================

bold "==============================================================================="
bold "1. Prerequisites, from $CRATE_BASE/requirements-ubuntu.txt"
bold "==============================================================================="
#echo "whoami: `whoami`"
#echo "HOME: $HOME"
echo "XDG_CACHE_HOME: $XDG_CACHE_HOME"
while read package; do
    require_debian_package $package
done <"$CRATE_BASE/requirements-ubuntu.txt"
reassure "OK"

bold "==============================================================================="
bold "2. Downloading and installing virtualenv into a temporary space"
bold "==============================================================================="
VENV_URL_BASE=https://pypi.python.org/packages/source/v/virtualenv
TEMPDIR=`mktemp -d`
pushd $TEMPDIR
curl -O $VENV_URL_BASE/virtualenv-$VENV_VERSION.tar.gz
# Extract it
tar xzf virtualenv-$VENV_VERSION.tar.gz
reassure "OK"

bold "==============================================================================="
bold "3. Using system Python ($PYTHON) and downloaded virtualenv software to make $CRATE_VIRTUALENV"
bold "==============================================================================="
"$PYTHON" virtualenv-$VENV_VERSION/virtualenv.py "$CRATE_VIRTUALENV"
# Install virtualenv into the environment.
"$CRATE_VIRTUALENV/bin/pip" install virtualenv-$VENV_VERSION.tar.gz
popd
reassure "OK"

bold "==============================================================================="
bold "4. Cleanup"
bold "==============================================================================="
rm -rf $TEMPDIR
reassure "OK"

bold "==============================================================================="
bold "5. Make virtual environment set PYTHONPATH etc., to point to us"
bold "==============================================================================="
cat << END_HEREDOC >> $CRATE_VIRTUALENV/bin/activate
export OLD_PYTHONPATH="\$PYTHONPATH"
export PYTHONPATH="$CRATE_BASE"
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
reassure "OK"

bold "==============================================================================="
bold "6. Activate our virtual environment, $CRATE_VIRTUALENV"
bold "==============================================================================="
source "$CRATE_VIRTUALENV/bin/activate"
# ... now "python", "pip", etc. refer to the virtual environment
echo "python is now: `which python`"
python --version
echo "pip is now: `which pip`"
pip --version
reassure "OK"

bold "==============================================================================="
bold "7. Install dependencies"
bold "==============================================================================="
pip install -r $CRATE_BASE/requirements.txt
reassure "OK"

reassure "--- Virtual environment installed successfully"
