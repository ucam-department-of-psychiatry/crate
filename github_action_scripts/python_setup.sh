#!/usr/bin/env bash

set -eux -o pipefail

cd "${GITHUB_WORKSPACE}"
python -m venv "${HOME}/venv"
PYTHON=${HOME}/venv/bin/python
${PYTHON} -VV
${PYTHON} -m site
${PYTHON} -m ensurepip --upgrade
${PYTHON} -m pip install -U pip setuptools
echo dumping pre-installed packages
${PYTHON} -m pip freeze
echo installing pip packages
${PYTHON} -m pip install -e ".[dev]"
echo installing database backends
${PYTHON} -m pip install mssql-django mysqlclient psycopg2 pyodbc pymssql
