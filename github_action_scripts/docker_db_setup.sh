#!/usr/bin/env bash

# Run from .github/workflows/integration-tests.yml
# Start the requested database engine in a Docker container

set -euxo pipefail

if [ $# -lt 1 ]; then
   echo "Usage: $0 <mysql|postgres|sqlserver> [host port]"
   exit 1
fi

ENGINE=$1
HOST_PORT=$2

if [ "$HOST_PORT" != "" ]; then
    PORTARGS="--hostport ${HOST_PORT}"
else
    PORTARGS=""
fi

PYTHON="${HOME}/venv/bin/python"
${PYTHON} ${GITHUB_WORKSPACE}/crate_anon/integration_tests/test_workflow.py --engine ${ENGINE} ${PORTARGS} startengine
