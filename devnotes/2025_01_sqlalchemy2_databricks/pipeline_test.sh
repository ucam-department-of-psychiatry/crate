#!/bin/bash

# Run a battery of CRATE tests locally.

set -ex

if [ -z "$TMP_CRATE_DEMO_DATABASE_URL" ]; then
    echo "Please set environment variable TMP_CRATE_DEMO_DATABASE_URL first."
    exit 1
fi

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
TEST_ROOT_DIR="${SCRIPT_DIR}/../.."
cd "${TEST_ROOT_DIR}"

crate_make_demo_database "${TMP_CRATE_DEMO_DATABASE_URL}"
crate_anon_draft_dd
crate_anonymise --full
crate_anonymise --incremental
crate_nlp --nlpdef crate_biomarkers --full
crate_nlp --nlpdef crate_biomarkers --incremental
crate_researcher_report ~/Downloads/tmp_crate_researcher_report.pdf

pytest  # Do this last: warnings (which may be OK) cause exit code failure.
