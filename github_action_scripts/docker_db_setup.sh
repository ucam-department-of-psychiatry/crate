#!/usr/bin/env bash

# Run from .github/workflows/integration-tests.yml
# Start the requested database engine in a Docker container

set -euxo pipefail

if [ "$#" != "2" ]; then
   echo "Usage: $0 <mysql|postgres|sqlserver> <port>"
   exit 1
fi

ENGINE=$1
PORT=$2

PYTHON="${HOME}/venv/bin/python"
${PYTHON} ${GITHUB_WORKSPACE}/crate_anon/integration_tests/test_workflow.py --engine ${ENGINE} startengine
