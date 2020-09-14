#!/usr/bin/env bash
# docs/source/nlp/run_gate_kcl_pharmacotherapy_via_crate.sh

set -e

if [ -z "${CRATE_PACKAGE_ROOT}" ]; then
    echo "Aborting: environment variable CRATE_PACKAGE_ROOT is unset or blank"
    exit 1
fi
if [ -z "${GATE_HOME}" ]; then
    echo "Aborting: environment variable GATE_HOME is unset or blank"
    exit 1
fi
if [ -z "${CRATE_GATE_PLUGIN_FILE}" ]; then
    echo "Aborting: environment variable CRATE_GATE_PLUGIN_FILE is unset or blank"
    exit 1
fi
if [ -z "${KCL_PHARMACOTHERAPY_DIR}" ]; then
    echo "Aborting: environment variable KCL_PHARMACOTHERAPY_DIR is unset or blank"
    exit 1
fi

CRATE_NLP_JAVA_CLASS_DIR=${CRATE_PACKAGE_ROOT}/nlp_manager/compiled_nlp_classes

java \
    -classpath "${CRATE_NLP_JAVA_CLASS_DIR}:${GATE_HOME}/bin/*:${GATE_HOME}/lib/*" \
    -Dgate.home="${GATE_HOME}" \
    CrateGatePipeline \
    --pluginfile "${CRATE_GATE_PLUGIN_FILE}" \
    --gate_app "${KCL_PHARMACOTHERAPY_DIR}/application.xgapp" \
    --include_set Output \
    --annotation Prescription \
    --input_terminator STOP \
    --output_terminator END_OF_NLP_OUTPUT_RECORD \
    --suppress_gate_stdout \
    --show_contents_on_crash \
    -v -v
