#!/usr/bin/env bash

CRATE_NLP_JAVA_CLASS_DIR=${CRATE_SOURCE_ROOT}/crate_anon/nlp_manager/compiled_nlp_classes

java \
    -classpath "${CRATE_NLP_JAVA_CLASS_DIR}":"${GATE_DIR}/bin/gate.jar":"${GATE_DIR}/lib/*" \
    -Dgate.home="${GATE_DIR}" \
    CrateGatePipeline \
    --gate_app "${GATE_LEWY_BODY_DIAGNOSIS_DIR}/application.xgapp" \
    --set_annotation "" DiagnosisAlmost \
    --set_annotation Automatic cDiagnosis \
    --input_terminator END_OF_TEXT_FOR_NLP \
    --output_terminator END_OF_NLP_OUTPUT_RECORD \
    --suppress_gate_stdout \
    --show_contents_on_crash \
    -v -v
