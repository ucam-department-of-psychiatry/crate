#!/usr/bin/env bash

# Run from .github/workflows/python-checks.yml
# Install CRATE python packages and run various tests

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
echo checking packages for conflicts
python -m pip check
echo installing vulnerability checker
python -m pip install safety
echo checking packages for vulnerabilities
# All of these vulnerabilities look either harmless or very low risk
# 51457 py no fix yet
#       https://github.com/pytest-dev/py/issues/287
# 51668 sqlalchemy fix in 2.0 beta, we don't log Engine.URL()
#       https://github.com/sqlalchemy/sqlalchemy/issues/8567
# 52495 setuptools fix in 65.5.1, we'll be careful not to
#       install malicious packages.
safety check --full-report --ignore=51457 --ignore=51668 --ignore=52495
echo checking python formatting
black --line-length 79 --diff --check .
echo checking python for style and errors
flake8 --config=setup.cfg .
echo running tests
export CRATE_RUN_WITHOUT_LOCAL_SETTINGS=True
pytest -v
