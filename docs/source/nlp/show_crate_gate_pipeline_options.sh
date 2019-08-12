#!/usr/bin/env bash

CRATE_NLP_JAVA_CLASS_DIR=${CRATE_SOURCE_ROOT}/crate_anon/nlp_manager/compiled_nlp_classes

java \
    -classpath "${CRATE_NLP_JAVA_CLASS_DIR}":"${GATE_DIR}/bin/gate.jar":"${GATE_DIR}/lib/*" \
    -Dgate.home="${GATE_DIR}" \
    CrateGatePipeline \
    --help \
    -v -v

exit 0
