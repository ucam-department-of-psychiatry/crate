#!/bin/bash

set -euxo pipefail

# TODO: Set to 1 when it is working
UPDATE_PACKAGES=0
UPDATE_VENV=0

CRATE_HOME=$HOME/crate
CRATE_INSTALLER_VENV=$HOME/.local/share/virtualenv/crate-installer

INSTALLER_HOME="$( cd "$( dirname "$0" )" && pwd )"

if [ "$UPDATE_PACKAGES" -eq "1" ]; then
    sudo apt-get update
    sudo apt -y install python3-virtualenv python3-venv
fi

if [ ! -d "${CRATE_INSTALLER_VENV}" ]; then
    python3 -m venv ${CRATE_INSTALLER_VENV}
fi

source ${CRATE_INSTALLER_VENV}/bin/activate

if [ "$UPDATE_VENV" -eq "1" ]; then
    python -m pip install -U pip setuptools
    python -m pip install -r ${INSTALLER_HOME}/installer-requirements.txt
fi

python $INSTALLER_HOME/installer.py
