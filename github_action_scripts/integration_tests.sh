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
# Install wkhtmltopdf on headless ubuntu 18 vps
# https://gist.github.com/lobermann/ca0e7bb2558b3b08923c6ae2c37a26ce
# 429 = Too many requests. Unfortunately wget doesn't read the
# Retry-after header so just wait 5 minutes
wget --retry-on-http-error=429 --waitretry=300 --tries=20 https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.bionic_amd64.deb
sudo apt-get -y install fontconfig libxrender1 xfonts-75dpi xfonts-base
sudo dpkg -i wkhtmltox_0.12.6-1.bionic_amd64.deb

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