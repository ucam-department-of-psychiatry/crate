#!/usr/bin/env bash

# Run from .github/workflows/gate.yml
# Install CRATE python packages and build the GATE Java interface

set -euxo pipefail

if [ "$#" != "1" ]; then
   echo "Usage: $0 <gate version>"
   exit 1
fi

GATE_VERSION=$1
TMPDIR=/tmp

CRATE_VENV_BIN="${HOME}/venv/bin"

GATE_XML_FILENAME=${TMPDIR}/gate_auto_install.xml
GATE_HOME=${HOME}/gate

KCL_PHARMACOTHERAPY_PARENT_DIR=${HOME}/kcl_pharmacotherapy
KCL_PHARMACOTHERAPY_DIR=${KCL_PHARMACOTHERAPY_PARENT_DIR}/brc-gate-pharmacotherapy

CRATE_GATE_PLUGIN_FILE=${GITHUB_WORKSPACE}/crate_anon/nlp_manager/specimen_gate_plugin_file.ini

${CRATE_VENV_BIN}/crate_nlp_write_gate_auto_install_xml --filename ${GATE_XML_FILENAME} --version ${GATE_VERSION} --gatedir "${GATE_HOME}"
wget -O "${TMPDIR}/gate-installer.jar" https://github.com/GateNLP/gate-core/releases/download/v${GATE_VERSION}/gate-developer-${GATE_VERSION}-installer.jar

java -jar "${TMPDIR}/gate-installer.jar" ${GATE_XML_FILENAME}
wget -O "${TMPDIR}/brc-gate-pharmacotherapy.zip" https://github.com/KHP-Informatics/brc-gate-pharmacotherapy/releases/download/1.1/brc-gate-pharmacotherapy.zip
unzip "${TMPDIR}/brc-gate-pharmacotherapy.zip" -d "${KCL_PHARMACOTHERAPY_PARENT_DIR}"

${CRATE_VENV_BIN}/crate_nlp_build_gate_java_interface --gatedir "${GATE_HOME}"
NLP_MANAGER_DIR=${GITHUB_WORKSPACE}/crate_anon/nlp_manager
echo -e "Katherine Johnson\nEND" | java -classpath "${NLP_MANAGER_DIR}/gate_log_config/:${NLP_MANAGER_DIR}/compiled_nlp_classes:${GATE_HOME}/bin/gate.jar:${GATE_HOME}/lib/*" CrateGatePipeline -a Person -a Location -it END -ot END --demo --log_tag TEST | grep -P '^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} \[DEBUG\|CrateGatePipeline\|TEST\] _content:Katherine Johnson'
