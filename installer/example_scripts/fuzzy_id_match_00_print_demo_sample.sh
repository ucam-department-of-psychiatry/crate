#!/usr/bin/env bash

# installer/example_scripts/fuzzy_id_match_00_print_demo_sample.sh

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

DEMO_SAMPLE=${CRATE_CONTAINER_LINKAGE_DIR}/sample_source.csv

${PYTHON} "${CRATE_HOST_INSTALLER_BASE_DIR}/installer.py" exec "crate_fuzzy_id_match \
    print_demo_sample" \
    2>&1 \
    1>${DEMO_SAMPLE} \
    | tee "${CRATE_HOST_FUZZY_MATCH_DEMO_SAMPLE_LOG}"

echo "The demo CSV file has been written to ${DEMO_SAMPLE}"
