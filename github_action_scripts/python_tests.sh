#!/usr/bin/env bash

# Run from .github/workflows/python-tests.yml
# Install CRATE python packages and run pytest

set -eux -o pipefail

VENV_BIN="${HOME}/venv/bin"
PYTHON="${VENV_BIN}/python"
PYTEST="${VENV_BIN/pytest"

${PYTHON} -m pip install mysqlclient
cd "${GITHUB_WORKSPACE}"
${PYTEST} -v
