#!/usr/bin/env bash

CRATE_NLP_JAVA_CLASS_DIR=${CRATE_SOURCE_ROOT}/crate_anon/nlp_manager/compiled_nlp_classes

java \
    -classpath "${CRATE_NLP_JAVA_CLASS_DIR}":"${MEDEX_DIR}/bin":"${MEDEX_DIR}/lib/*" \
    CrateMedexPipeline \
    --help \
    -v -v

exit 0
