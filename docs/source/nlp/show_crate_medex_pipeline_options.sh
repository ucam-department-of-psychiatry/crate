#!/usr/bin/env bash
set -e

if [ -z "${CRATE_SOURCE_ROOT}" ]; then
    echo "Aborting: environment variable CRATE_SOURCE_ROOT is unset or blank"
    exit 1
fi
if [ -z "${MEDEX_DIR}" ]; then
    echo "Aborting: environment variable MEDEX_DIR is unset or blank"
    exit 1
fi

CRATE_NLP_JAVA_CLASS_DIR=${CRATE_SOURCE_ROOT}/crate_anon/nlp_manager/compiled_nlp_classes

java \
    -classpath "${CRATE_NLP_JAVA_CLASS_DIR}":"${MEDEX_DIR}/bin":"${MEDEX_DIR}/lib/*" \
    CrateMedexPipeline \
    --help \
    -v -v

exit 0
