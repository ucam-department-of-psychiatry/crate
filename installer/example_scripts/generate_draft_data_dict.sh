#!/usr/bin/env bash

# installer/example_scripts/generate_draft_data_dict.sh

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

# Example script to generate a draft Data Dictionary to use with anonymisation.


set -euo pipefail

THISDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
# shellcheck source-path=SCRIPTDIR source=set_crate_environment_vars
source "${THISDIR}"/set_crate_environment_vars

DRAFT_DD=${CRATE_HOST_CONFIG_DIR}/crate_dd_DRAFT.tsv

${PYTHON} "${CRATE_HOST_INSTALLER_BASE_DIR}/installer.py" exec "crate_anon_draft_dd \
    --config ${CRATE_CONTAINER_CONFIG_ANON} \
    --verbose" \
    2>&1 \
    1>${DRAFT_DD} \
    | tee "${CRATE_HOST_DDGEN_LOG}"

echo If successful, see "${DRAFT_DD}" for the draft data dictionary.
echo A log was kept in "${CRATE_HOST_DDGEN_LOG}"
