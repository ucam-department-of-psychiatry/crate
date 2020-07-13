#!/usr/bin/env bash
set -e

if [ -z "${CRATE_SOURCE_ROOT}" ]; then
    echo "Aborting: environment variable CRATE_SOURCE_ROOT is unset or blank"
    exit 1
fi
if [ -z "${GATE_DIR}" ]; then
    echo "Aborting: environment variable GATE_DIR is unset or blank"
    exit 1
fi

CRATE_NLP_JAVA_CLASS_DIR=${CRATE_SOURCE_ROOT}/crate_anon/nlp_manager/compiled_nlp_classes

java \
    -classpath "${CRATE_NLP_JAVA_CLASS_DIR}":"${GATE_DIR}/bin/gate.jar":"${GATE_DIR}/lib/*" \
    -Dgate.home="${GATE_DIR}" \
    CrateGatePipeline \
    --help \
    -v -v

exit 0
