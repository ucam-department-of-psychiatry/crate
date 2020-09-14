#!/usr/bin/env bash
# docs/source/nlp/show_crate_gate_medex_options.sh

set -e

if [ -z "${CRATE_PACKAGE_ROOT}" ]; then
    echo "Aborting: environment variable CRATE_PACKAGE_ROOT is unset or blank"
    exit 1
fi
if [ -z "${MEDEX_DIR}" ]; then
    echo "Aborting: environment variable MEDEX_DIR is unset or blank"
    exit 1
fi

CRATE_NLP_JAVA_CLASS_DIR=${CRATE_PACKAGE_ROOT}/nlp_manager/compiled_nlp_classes

java \
    -classpath "${CRATE_NLP_JAVA_CLASS_DIR}:${MEDEX_DIR}/bin:${MEDEX_DIR}/lib/*" \
    CrateMedexPipeline \
    --help \
    -v -v

exit 0
