#!/usr/bin/env bash

# Run from .github/workflows/python-tests.yml
# Install CRATE python packages and run pytest

set -euxo pipefail

usage() {
    echo "Usage: $0 <pytest executable> <mysql|postgres|sqlite|sqlserver> [port] [option]"
    exit 1
}


if [ "$#" -lt 2 ]; then
    usage
fi

PYTEST=$1
ENGINE=$2
SCHEME=
PORT=

if [ "$#" -gt 2 ]; then
    SCHEME=$3
fi

PORT=
if [ "$#" -gt 3 ]; then
    PORT=$4
fi

PYTEST_ARGS=(-v)
if [ "${ENGINE}" != "sqlite" ]; then
    if [ "${SCHEME}" != "mssql+pyodbc" ]; then
        if [ "${PORT}" == "" ]; then
            echo "You must specify a port for engine ${ENGINE}"
            exit 1
        fi

        ENGINE_IP=$(docker inspect crate_test_container_engine_"${ENGINE}" --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
    fi

    QUERY=
    if [ "${ENGINE}" == "mysql" ]; then
        QUERY="?charset=utf8"
    fi

    ANON_USER=administrator
    ANON_PASSWORD=8z3%3FI84%40mvBX
    PYTEST_ARGS+=(--anon-db-url)
    if [ "${SCHEME}" == "mssql+pyodbc" ]; then
        ANON_HOST=anondb
        ANON_PATH=
    else
        ANON_HOST="${ENGINE_IP}:${PORT}"
        ANON_PATH="/anondb${QUERY}"
    fi
    PYTEST_ARGS+=("${SCHEME}://${ANON_USER}:${ANON_PASSWORD}@${ANON_HOST}${ANON_PATH}")

    SECRET_USER=administrator
    SECRET_PASSWORD=8z3%3FI84%40mvBX
    PYTEST_ARGS+=(--secret-db-url)
    if [ "${SCHEME}" == "mssql+pyodbc" ]; then
        SECRET_HOST=secretdb
        SECRET_PATH=
    else
        SECRET_HOST="${ENGINE_IP}:${PORT}"
        SECRET_PATH="/secretdb${QUERY}"
    fi
    PYTEST_ARGS+=("${SCHEME}://${SECRET_USER}:${SECRET_PASSWORD}@${SECRET_HOST}${SECRET_PATH}")

    SOURCE_USER=administrator
    SOURCE_PASSWORD=8z3%3FI84%40mvBX
    PYTEST_ARGS+=(--source-db-url)
    if [ "${SCHEME}" == "mssql+pyodbc" ]; then
        SOURCE_HOST=sourcedb
        SOURCE_PATH=
    else
        SOURCE_HOST="${ENGINE_IP}:${PORT}"
        SOURCE_PATH="/sourcedb${QUERY}"
    fi
    PYTEST_ARGS+=("${SCHEME}://${SOURCE_USER}:${SOURCE_PASSWORD}@${SOURCE_HOST}${SOURCE_PATH}")
fi

echo running tests
THIS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
PROJECT_ROOT=${THIS_DIR}/..
cd "${PROJECT_ROOT}"/crate_anon
export CRATE_NLP_WEB_CONFIG=${THIS_DIR}/test_nlp_web_config.ini
export ODBCINI=${THIS_DIR}/odbc_user_host.ini
${PYTEST} ${PYTEST_ARGS[*]}
