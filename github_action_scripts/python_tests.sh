#!/usr/bin/env bash

# Run from .github/workflows/python-tests.yml
# Install CRATE python packages and run pytest

set -euo pipefail

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

    ENGINE_IP=$(docker inspect crate_test_container_engine_"${ENGINE}" --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')

    ANON_USER=administrator
    ANON_PASSWORD=8z3%3FI84%40mvBX
    ANON_DB=anondb
    ANON_DB_URL="${SCHEME}://${ANON_USER}:${ANON_PASSWORD}@${ENGINE_IP}:${PORT}/${ANON_DB}${QUERY}"

    SECRET_USER=administrator
    SECRET_PASSWORD=8z3%3FI84%40mvBX
    SECRET_DB=secretdb
    SECRET_DB_URL="${SCHEME}://${SECRET_USER}:${SECRET_PASSWORD}@${ENGINE_IP}:${PORT}/${SECRET_DB}${QUERY}"

    SOURCE_USER=administrator
    SOURCE_PASSWORD=8z3%3FI84%40mvBX
    SOURCE_DB=sourcedb
    SOURCE_DB_URL="${SCHEME}://${SOURCE_USER}:${SOURCE_PASSWORD}@${ENGINE_IP}:${PORT}/${SOURCE_DB}${QUERY}"

    DB_OPTION="--anon-db-url ${ANON_DB_URL} --secret_db_url ${SECRET_DB_URL} --source-db-url ${SOURCE_DB_URL}"
fi

echo running tests
cd "${GITHUB_WORKSPACE}"/crate_anon
export CRATE_NLP_WEB_CONFIG=${GITHUB_WORKSPACE}/github_action_scripts/test_nlp_web_config.ini

VENV_BIN="${HOME}/venv/bin"
PYTEST="${VENV_BIN}/pytest"

${PYTEST} -v "${DB_OPTION}"
