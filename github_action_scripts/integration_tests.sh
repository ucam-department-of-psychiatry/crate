#!/usr/bin/env bash

# Run from .github/workflows/integration-tests.yml
# Install CRATE python packages and run longer end-to-end tests

set -euxo pipefail

if [ "$#" != "1" ]; then
   echo "Usage: $0 <mysql|postgres|sqlserver>"
   exit 1
fi

ENGINE=$1

PYTHON="${HOME}/venv/bin/python"
${PYTHON} ${GITHUB_WORKSPACE}/crate_anon/integration_tests/test_workflow.py --engine ${ENGINE} testcrate
