#!/usr/bin/env bash

# Run from .github/workflows/python-checks.yml
# Install CRATE python packages and run various checks

set -eux -o pipefail

VENV_BIN="${HOME}/venv/bin"
PYTHON="${VENV_BIN}/python"
SAFETY="${VENV_BIN}/safety"

${PYTHON} -m pip install mysqlclient
echo checking packages for conflicts
${PYTHON} -m pip check
echo installing vulnerability checker
${PYTHON} -m pip install safety
echo checking packages for vulnerabilities
# All of these vulnerabilities look either harmless or very low risk
# 51668 sqlalchemy fix in 2.0 beta, we don't log Engine.URL()
#       https://github.com/sqlalchemy/sqlalchemy/issues/8567
# 52495 setuptools fix in 65.5.1, we'll be careful not to
#       install malicious packages.
# 67599 pip. Disputed and only relevant if using --extra-index-url,
#       which we're not.
# 70612 jinja2. The maintainer and multiple third parties
#       believe that this vulnerability isn't valid because
#       users shouldn't use untrusted templates without
#       sandboxing.
${SAFETY} check --full-report --ignore=51668 --ignore=52495 --ignore=67599 --ignore=70612
