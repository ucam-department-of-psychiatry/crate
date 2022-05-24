#!/usr/bin/env bash

# Run from .github/workflows/python-checks.yml
# Install CRATE python packages and run various tests

set -eux -o pipefail

cd "${GITHUB_WORKSPACE}"
python -m venv "${HOME}/venv"
source "${HOME}/venv/bin/activate"
python -VV
python -m site
python -m pip install -U pip
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
# 44715 numpy fixed in 1.22 https://github.com/numpy/numpy/issues/19038
# 44716 numpy fixed in 1.22 https://github.com/numpy/numpy/issues/19000
# 44717 numpy fixed in 1.22 https://github.com/numpy/numpy/issues/18993
safety check --full-report -i 44715 -i 44716 -i 44717
echo checking python formatting
black --line-length 79 --diff --check .
echo checking python for style and errors
flake8 --config=setup.cfg .
echo running tests
export CRATE_RUN_WITHOUT_LOCAL_SETTINGS=True
pytest -v
