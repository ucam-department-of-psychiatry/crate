#!/usr/bin/env bash

# Run from .github/workflows/python-checks.yml
# Install CRATE python packages and run various checks

set -eux -o pipefail

VENV_BIN="${HOME}/venv/bin"
PYTHON="${VENV_BIN}/python"
SAFETY="${VENV_BIN}/safety"

# Duplicate Docker setup (see crate.Dockerfile)
${PYTHON} -m pip install mssql-django==1.5 mysqlclient==1.4.6 psycopg2==2.8.5 pyodbc==4.0.39

echo checking packages for conflicts
${PYTHON} -m pip check
echo installing vulnerability checker
${PYTHON} -m pip install safety
echo checking packages for vulnerabilities
# All of these vulnerabilities look either harmless or very low risk
# 67599 pip. Disputed and only relevant if using --extra-index-url,
#       which we're not.
# 70612 jinja2. The maintainer and multiple third parties
#       believe that this vulnerability isn't valid because
#       users shouldn't use untrusted templates without
#       sandboxing.
${SAFETY} check --full-report --ignore=67599 --ignore=70612
