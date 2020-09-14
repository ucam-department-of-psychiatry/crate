#!/usr/bin/env bash
# docs/source/nlp/prepare_umls_for_bioyodie.sh

set -e

function syntax {
    echo "usage: $0 UMLS_ZIP DEST_DIR"
    echo
    echo "Arguments:"
    echo
    echo "  UMLS_ZIP"
    echo "    Filename of ZIP file downloaded from"
    echo "    https://www.nlm.nih.gov/research/umls/licensedcontent/umlsknowledgesources.html,"
    echo "    e.g. /path/to/umls-2017AA-full.zip"
    echo
    echo "  DEST_DIR"
    echo
}

export TMPDIR="/tmp/crate_tmp"
mkdir -p "${TMPDIR}"

UMLS_ZIP=$1
DEST_DIR=$2

if [ -z "${CRATE_PACKAGE_ROOT}" ]; then
    syntax()
    exit 1
fi
if [ -z "${GATE_HOME}" ]; then
    echo "Aborting: environment variable GATE_HOME is unset or blank"
    exit 1
fi

