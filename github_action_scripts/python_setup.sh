#!/usr/bin/env bash

set -eux -o pipefail

cd "${GITHUB_WORKSPACE}"
python -m venv "${HOME}/venv"
source "${HOME}/venv/bin/activate"
python -VV
python -m site
python -m ensurepip --upgrade
python -m pip install -U setuptools
echo dumping pre-installed packages
python -m pip freeze
echo installing pip packages
python -m pip install -e .
echo installing database backends
python -m pip install mssql-django mysqlclient psycopg2 pyodbc pymssql
