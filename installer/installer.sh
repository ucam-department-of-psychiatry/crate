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

mkdir -p ${CRATE_HOME}
cd ${CRATE_HOME}

# Production:
# curl -L https://github.com/RudolfCardinal/crate/releases/latest/download/crate.zip

# Pre-production
curl -L https://github.com/RudolfCardinal/crate/archive/refs/tags/installer-test-1/crate.zip
unzip crate.zip

# Production
INSTALLER_HOME = ${CRATE_HOME}/installer

# Development
# INSTALLER_HOME="$( cd "$( dirname "$0" )" && pwd )"

# Prerequisites (platform dependent) :
# sudo apt-get update
# sudo apt -y install python3-virtualenv python3-venv

CRATE_INSTALLER_PYTHON=${CRATE_INSTALLER_PYTHON:-python3}

if [ ! -d "${CRATE_INSTALLER_VENV}" ]; then
    # TOOO: Option to rebuild venv
    ${CRATE_INSTALLER_PYTHON} -m venv ${CRATE_INSTALLER_VENV}
fi

source ${CRATE_INSTALLER_VENV}/bin/activate

PYTHON_VERSION_OK=$(python3 -c 'import sys; print(sys.version_info.major >=3 and sys.version_info.minor >= 7)')

if [ "${PYTHON_VERSION_OK}" == "False" ]; then
    python --version
    echo "You need at least Python 3.7 to run the installer."
    exit 1
fi

python -m pip install -U pip setuptools
python -m pip install -r ${INSTALLER_HOME}/installer-requirements.txt


python $INSTALLER_HOME/installer.py
