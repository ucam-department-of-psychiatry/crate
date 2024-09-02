#!/usr/bin/env bash

# Run from .github/workflows/python-tests.yml
# Install CRATE python packages and run pytest

set -euxo pipefail

ENGINE=$1
if [ "${ENGINE}" == "" ]; then
   echo "Usage: $0 <mysql|postgres|sqlite|sqlserver> [port]"
    exit 1
fi

if [ "${ENGINE}" == "sqlite" ]; then
    DB_OPTION=""
else
    QUERY=""
    PORT=$2

    if [ "${PORT}" == "" ]; then
        echo "You must specify a port for engine ${ENGINE}"
        exit 1
    fi

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

    ENGINE_IP=$(docker inspect crate_test_container_engine_${ENGINE} --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
    TEST_USER=tester
    TEST_PASSWORD=Qcig%40cuW%3Fmyo
    TEST_DB=testdb
    DB_OPTION="--db-url ${SCHEME}://${TEST_USER}:${TEST_PASSWORD}@${ENGINE_IP}:${PORT}/${TEST_DB}${QUERY}"
fi

echo running tests
cd "${GITHUB_WORKSPACE}"/crate_anon
export CRATE_RUN_WITHOUT_LOCAL_SETTINGS=True
export CRATE_NLP_WEB_CONFIG=${GITHUB_WORKSPACE}/github_action_scripts/test_nlp_web_config.ini

VENV_BIN="${HOME}/venv/bin"
PYTEST="${VENV_BIN}/pytest"

${PYTEST} -v ${DB_OPTION}
