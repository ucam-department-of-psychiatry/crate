#!/usr/bin/env bash

# Run from .github/workflows/python-checks.yml
# Install CRATE python packages and run various checks

set -eux -o pipefail

VENV_BIN="${HOME}/venv/bin"
PYTHON="${VENV_BIN}/python"
SAFETY="${VENV_BIN}/safety"

# Duplicate Docker setup (see crate.Dockerfile)
${PYTHON} -m pip install mssql-django==1.7.1 mysqlclient==1.4.6 psycopg2==2.9.10 pyodbc==5.4.0

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
# SFTY-20260721-58460 setuptools. CVE-2026-59890. Fixed in 83.0.0. Relevant to macOS APFS
#                     and HFS+ filesystems. We can't upgrade until Pyramid removes its
#                     dependency on pkg_resources (https://github.com/Pylons/pyramid/issues/3731).
#                     Nearly complete as of 2026-08-28.
# SFTY-20261017-72390 filelock. Safety is pulling in an old version but we don't
# SFTY-20261017-54654           use it outside of development.
# SFTY-20261017-57659
# SFTY-20261020-25530
# SFTY-20261020-11422

${SAFETY} check --full-report \
    --ignore=67599 \
    --ignore=70612 \
    --ignore=SFTY-20260721-58460 \
    --ignore=SFTY-20261017-72390 \
    --ignore=SFTY-20261017-54654 \
    --ignore=SFTY-20261017-57659 \
    --ignore=SFTY-20261020-25530 \
    --ignore=SFTY-20261020-11422
