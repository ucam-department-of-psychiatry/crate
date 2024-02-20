#!/usr/bin/env bash

set -eux -o pipefail

cd "${GITHUB_WORKSPACE}"
python -m venv "${HOME}/venv"
source "${HOME}/venv/bin/activate"
python -VV
python -m site
python -m pip install -U pip setuptools
echo dumping pre-installed packages
python -m pip freeze
echo installing pip packages
python -m pip install -e .
echo installing database backends
# Same versions as in docker/dockerfiles/crate.Dockerfile
python -m pip install mssql-django==1.2 mysqlclient==1.4.6 psycopg2==2.8.5 pyodbc==4.0.30 pymssql==2.2.11
