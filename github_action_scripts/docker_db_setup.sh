#!/usr/bin/env bash

# Run from .github/workflows/integration-tests.yml
# Start the requested database engine in a Docker container

set -euxo pipefail

if [ $# -lt 1 ]; then
   echo "Usage: $0 <mysql|postgres|sqlserver> [host port]"
   exit 1
fi

ENGINE=$1

PORTARGS=""

if [ $# -eq 2 ]; then
    HOST_PORT=$2
    PORTARGS="--hostport ${HOST_PORT}"
fi

PYTHON="${HOME}/venv/bin/python"
${PYTHON} ${GITHUB_WORKSPACE}/crate_anon/integration_tests/test_workflow.py --engine ${ENGINE} ${PORTARGS} startengine
