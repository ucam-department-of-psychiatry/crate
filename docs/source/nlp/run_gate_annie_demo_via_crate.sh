#!/usr/bin/env bash
# docs/source/nlp/run_gate_annie_demo_via_crate.sh

set -e

if [ -z "${CRATE_PACKAGE_ROOT}" ]; then
    echo "Aborting: environment variable CRATE_PACKAGE_ROOT is unset or blank"
    exit 1
fi
if [ -z "${GATE_HOME}" ]; then
    echo "Aborting: environment variable GATE_HOME is unset or blank"
    exit 1
fi

CRATE_NLP_JAVA_CLASS_DIR=${CRATE_PACKAGE_ROOT}/nlp_manager/compiled_nlp_classes

# Note the unrealistic use of "STOP" as an end-of-input marker. Don't use that for real!

java \
    -classpath "${CRATE_NLP_JAVA_CLASS_DIR}:${GATE_HOME}/bin/*:${GATE_HOME}/lib/*" \
    -Dgate.home="${GATE_HOME}" \
    CrateGatePipeline \
    --annotation Person \
    --annotation Location \
    --input_terminator STOP \
    --output_terminator END_OF_NLP_OUTPUT_RECORD \
    --log_tag . \
    -v -v \
    --demo
