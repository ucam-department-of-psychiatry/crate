#!/usr/bin/env bash

CRATE_NLP_JAVA_CLASS_DIR=${CRATE_SOURCE_ROOT}/crate_anon/nlp_manager/compiled_nlp_classes

# Note the unrealistic use of "STOP" as an end-of-input marker. Don't use that for real!

java \
    -classpath "${CRATE_NLP_JAVA_CLASS_DIR}":"${GATE_DIR}/bin/gate.jar":"${GATE_DIR}/lib/*" \
    -Dgate.home="${GATE_DIR}" \
    CrateGatePipeline \
    -g "${GATE_DIR}/plugins/ANNIE/ANNIE_with_defaults.gapp" \
    -a Person \
    -a Location \
    -it STOP \
    -ot END_OF_NLP_OUTPUT_RECORD \
    -lt . \
    -v -v
