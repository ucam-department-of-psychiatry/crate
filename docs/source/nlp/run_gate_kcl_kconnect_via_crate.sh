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
if [ -z "${CRATE_GATE_PLUGIN_FILE}" ]; then
    echo "Aborting: environment variable CRATE_GATE_PLUGIN_FILE is unset or blank"
    exit 1
fi
if [ -z "${KCONNECT_DIR}" ]; then
    echo "Aborting: environment variable KCONNECT_DIR is unset or blank"
    exit 1
fi

CRATE_NLP_JAVA_CLASS_DIR=${CRATE_SOURCE_ROOT}/crate_anon/nlp_manager/compiled_nlp_classes

# todo: Bug: this (run_gate_kcl_connect.sh) isn't working on Osprey; KConnect crashes

java \
    -classpath "${CRATE_NLP_JAVA_CLASS_DIR}":"${GATE_DIR}/bin/*":"${GATE_DIR}/lib/*" \
    -Dgate.home="${GATE_DIR}" \
    CrateGatePipeline \
    --pluginfile "${CRATE_GATE_PLUGIN_FILE}" \
    --gate_app "${KCONNECT_DIR}/main-bio/main-bio.xgapp" \
    --annotation Disease_or_Syndrome \
    --input_terminator END_OF_TEXT_FOR_NLP \
    --output_terminator END_OF_NLP_OUTPUT_RECORD \
    --suppress_gate_stdout \
    --show_contents_on_crash \
    -v -v
