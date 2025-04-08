#!/usr/bin/env bash

# installer/example_scripts/fuzzy_id_match_01_hash.sh

# ==============================================================================
#
#     Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
#     Created by Rudolf Cardinal (rnc1001@cam.ac.uk).
#
#     This file is part of CRATE.
#
#     CRATE is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     CRATE is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with CRATE. If not, see <https://www.gnu.org/licenses/>.
#
# ==============================================================================

# Example script to run full anonymisation on the databases specified in the
# anonymisation configuration.

set -euo pipefail

THISDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
# shellcheck source-path=SCRIPTDIR source=set_crate_environment_vars
source "${THISDIR}"/set_crate_environment_vars

PLAINTEXT_INPUT_CSV=${CRATE_CONTAINER_LINKAGE_DIR}/plaintext_input.csv
HASHED_OUTPUT_JSONL=${CRATE_CONTAINER_LINKAGE_DIR}/hashed_output.jsonl

# Recommended key length 32 bytes
HASH_KEY=fuzzy_id_match_default_hash_key_DO_NOT_USE_FOR_LIVE_DATA

# -- REMOVE ONCE CONFIGURED CORRECTLY
echo "Before using this script, please:"
echo "1. Download the ONSPD postcodes database ZIP file from https://geoportal.statistics.gov.uk/ and save the ZIP file in ${CRATE_HOST_LINKAGE_DIR}."
echo "2. Ensure you have created the CSV file ${PLAINTEXT_INPUT_CSV} (use fuzzy_match_00_print_demo_sample.sh for an example)."
echo "3. Set HASH_KEY above to one agreed by all providers wishing to link data."
exit 0
# -- REMOVE TO HERE


# crate_fuzzy_id_match hash --input identifiable-patients.csv --output hashed-patients.csv --hash_key fiftycharactersofgobbledegook

${PYTHON} "${CRATE_HOST_INSTALLER_BASE_DIR}/installer.py" exec "crate_fuzzy_id_match \
    hash \
    --hash_key ${HASH_KEY} \
    --input ${PLAINTEXT_INPUT_CSV} \
    --output ${HASHED_OUTPUT_JSONL} \
    --postcode_csv_filename ${POSTCODE_CSV_FILENAME}" \
    2>&1 \
    | tee "${CRATE_HOST_FUZZY_MATCH_HASH_LOG}"
