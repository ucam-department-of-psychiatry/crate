#!/bin/bash

set -euxo pipefail

# Prerequisites for Windows:
# Install WSL2
# Install Docker Desktop for Windows
# Enable WSL2 in Docker Desktop

# When we move to production the installation process will be:
# curl -L https://github.com/RudolfCardinal/crate/releases/latest/download/installer.sh | bash


CRATE_HOME=${HOME}/crate
CRATE_INSTALLER_VENV=${HOME}/.virtualenvs/crate-installer

# TODO:
# mkdir -p ${CRATE_HOME}
# cd ${CRATE_HOME}
# curl -L https://github.com/RudolfCardinal/crate/releases/latest/download/crate.zip
# unzip crate.zip

# INSTALLER_HOME = ${CRATE_HOME}/installer
INSTALLER_HOME="$( cd "$( dirname "$0" )" && pwd )"

# Prerequisites (platform dependent) :
# sudo apt-get update
# sudo apt -y install python3-virtualenv python3-venv

if [ ! -d "${CRATE_INSTALLER_VENV}" ]; then
    python3 -m venv ${CRATE_INSTALLER_VENV}
fi

source ${CRATE_INSTALLER_VENV}/bin/activate

python -m pip install -U pip setuptools
python -m pip install -r ${INSTALLER_HOME}/installer-requirements.txt


python $INSTALLER_HOME/installer.py
