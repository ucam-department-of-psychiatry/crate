#!/bin/bash

CRATE_HOME=$HOME/crate
CRATE_INSTALLER_VENV=$HOME/.local/share/virtualenv/crate-installer

INSTALLER_HOME="$( cd "$( dirname "$0" )" && pwd )"

set -euxo pipefail

# sudo apt-get update
# sudo apt -y install python3-virtualenv python3-venv

if [ ! -d "${CRATE_INSTALLER_VENV}" ]; then
    python3 -m venv ${CRATE_INSTALLER_VENV}
fi

source ${CRATE_INSTALLER_VENV}/bin/activate
python -m pip install -U pip setuptools
python -m pip install -r ${INSTALLER_HOME}/installer-requirements.txt

python $INSTALLER_HOME/installer.py
