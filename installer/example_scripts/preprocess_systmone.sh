#!/usr/bin/env bash

# installer/example_scripts/preprocess_systmone.sh

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

# Example script to preprocess a RiO database prior to data dictionary
# generation and anonymisation.


set -euo pipefail

THISDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
# shellcheck source-path=SCRIPTDIR source=set_crate_environment_vars
source "${THISDIR}"/set_crate_environment_vars

# -- REMOVE ONCE CONFIGURED CORRECTLY
echo "Before using this script, please:"
echo "1. Ensure CRATE_SOURCE_SYSTMONE_DB_URL in set_crate_environment_vars points to your SystmOne database and the user has read/write access"
echo "2. Place a copy of the SystmOne specification in ${CRATE_CONTAINER_SYSTMONE_TPP_SRE_SPEC} (modify this path in set_crate_environment_vars if necessary)"
echo "3. Remove these lines from the script"
exit 0
# -- REMOVE TO HERE

${PYTHON} "${CRATE_HOST_INSTALLER_BASE_DIR}/installer.py" exec "crate_preprocess_systmone \
    --url ${CRATE_SOURCE_SYSTMONE_DB_URL} \
    --verbose \
    --systmone_context cpft_dw \
    --postcodedb ${CRATE_ONSPD_NAME}" \
    2>&1 \
    | tee "${CRATE_HOST_SYSTMONE_PREPROCESS_LOG}"
