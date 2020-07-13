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

# Note the unrealistic use of "STOP" as an end-of-input marker. Don't use that for real!

java \
    -classpath "${CRATE_NLP_JAVA_CLASS_DIR}":"${GATE_DIR}/bin/*":"${GATE_DIR}/lib/*" \
    -Dgate.home="${GATE_DIR}" \
    CrateGatePipeline \
    --annotation Person \
    --annotation Location \
    --input_terminator STOP \
    --output_terminator END_OF_NLP_OUTPUT_RECORD \
    --log_tag . \
    -v -v \
    --demo
