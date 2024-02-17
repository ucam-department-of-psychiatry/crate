#!/usr/bin/env bash

# Run from .github/workflows/integration-tests.yml
# Install CRATE python packages and run longer end-to-end tests

set -euxo pipefail

if [ "$#" != "2" ]; then
   echo "Usage: $0 <mysql|postgres|sqlserver> <port>"
   exit 1
fi

ENGINE=$1
PORT=$2

sudo apt -y install wait-for-it

PYTHON="${HOME}/venv/bin/python"
# Same versions as in docker/dockerfiles/crate.Dockerfile
${PYTHON} -m pip install mssql-django==1.2 mysqlclient==1.4.6 psycopg2==2.8.5 pyodbc==4.0.30 pymssql==2.2.11
${PYTHON} ${GITHUB_WORKSPACE}/crate_anon/integration_tests/test_workflow.py --engine ${ENGINE} startengine
ENGINE_IP=$(docker inspect crate_test_container_engine --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
wait-for-it "${ENGINE_IP}:${PORT}" --timeout=300

for i in {1..7}; do
    logs=$(docker logs crate_test_container_engine)
    if [[ "$logs" =~ ">>> Databases created. READY." ]]; then
        break
    fi
    if [ $i -eq 7 ]; then
        echo "Gave up waiting for the databases to be created. Exiting."
        exit 1
    fi
    sleep 2
done

${PYTHON} ${GITHUB_WORKSPACE}/crate_anon/integration_tests/test_workflow.py --engine ${ENGINE} testcrate
