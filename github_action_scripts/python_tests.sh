#!/usr/bin/env bash

# Run from .github/workflows/python-tests.yml
# Install CRATE python packages and run pytest

set -eux -o pipefail

VENV_BIN="${HOME}/venv/bin"
PYTHON="${VENV_BIN}/python"
PYTEST="${VENV_BIN}/pytest"

${PYTHON} -m pip install mysqlclient
cd "${GITHUB_WORKSPACE}"
echo running tests
export CRATE_RUN_WITHOUT_LOCAL_SETTINGS=True
export CRATE_NLP_WEB_CONFIG=${GITHUB_WORKSPACE}/github_action_scripts/test_nlp_web_config.ini
${PYTEST} -v
