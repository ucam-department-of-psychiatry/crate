#!/usr/bin/env bash

# Run from .github/workflows/integration-tests.yml
# Install CRATE python packages and run longer end-to-end tests

set -euxo pipefail

if [ "$#" != "2" ]; then
   echo "Usage: $0 <mysql|postgres|sqlserver> <port>"
   exit 1
fi

ENGINE=$0
PORT=$1

sudo apt -y install wait-for-it
PYTHON="${HOME}/venv/bin/python"
# Same versions as in docker/dockerfiles/crate.Dockerfile
${PYTHON} -m pip install mssql-django==1.2 mysqlclient==1.4.6 psycopg2==2.8.5 pyodbc==4.0.30
${PYTHON} ${GITHUB_WORKSPACE}/crate_anon/integration_tests/test_workflow.py --engine ${ENGINE} startengine
ENGINE_IP=$(docker inspect crate_test_container_engine --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
wait-for-it "${ENGINE_IP}:${PORT}" --timeout=300
${PYTHON} ${GITHUB_WORKSPACE}/crate_anon/integration_tests/test_workflow.py --engine ${ENGINE} testcrate
