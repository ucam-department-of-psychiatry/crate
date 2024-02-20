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
# Same versions as in docker/dockerfiles/crate.Dockerfile
${PYTHON} -m pip install mssql-django==1.2 mysqlclient==1.4.6 psycopg2==2.8.5 pyodbc==4.0.30 pymssql==2.2.11
${PYTHON} ${GITHUB_WORKSPACE}/crate_anon/integration_tests/test_workflow.py --engine ${ENGINE} startengine
