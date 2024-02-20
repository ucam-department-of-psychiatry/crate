#!/usr/bin/env bash

# Run from .github/workflows/python-tests.yml
# Install CRATE python packages and run pytest

set -euxo pipefail

if [ "$#" != "2" ]; then
   echo "Usage: $0 <mysql|postgres|sqlite|sqlserver> <port>"
   exit 1
fi

ENGINE=$1
PORT=$2

VENV_BIN="${HOME}/venv/bin"
PYTHON="${VENV_BIN}/python"
PYTEST="${VENV_BIN}/pytest"

${PYTHON} -m pip install mysqlclient
cd "${GITHUB_WORKSPACE}"/crate_anon
echo running tests
export CRATE_RUN_WITHOUT_LOCAL_SETTINGS=True
export CRATE_NLP_WEB_CONFIG=${GITHUB_WORKSPACE}/github_action_scripts/test_nlp_web_config.ini

ENGINE_IP=$(docker inspect crate_test_container_engine --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
TEST_USER=tester
TEST_PASSWORD=QcigecuW1myo
TEST_DB=testdb

QUERY=""

case ${ENGINE} in
    mysql)
        SCHEME="mysql+mysqldb"
        QUERY="?charset=utf8"
        ;;

    postgres)
        SCHEME="postgresql"
        ;;

    sqlserver)
        SCHEME="mssql+pymssql"
        ;;
esac

DB_OPTION=""

if [ "${ENGINE}" != "sqlite" ]; then
    DB_OPTION="--db-url ${SCHEME}://${TEST_USER}:${TEST_PASSWORD}@${ENGINE_IP}:${PORT}/${TEST_DB}${QUERY}"
fi


${PYTEST} -v ${DB_OPTION}
