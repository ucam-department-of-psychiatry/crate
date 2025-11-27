#!/bin/bash

# installer/example_scripts/crate_fuzzy_id_match.sh

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

# Execute a command (docker compose exec) within the CRATE Docker environment

set -euo pipefail

THISDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
# shellcheck source-path=SCRIPTDIR source=set_crate_environment_vars
source "${THISDIR}"/set_crate_environment_vars

${PYTHON} "${CRATE_HOST_INSTALLER_BASE_DIR}/installer.py" exec "crate_fuzzy_id_match \
    compare_hashed_to_plaintext \
    --forename_cache_filename=${CRATE_CONTAINER_FORENAME_CACHE_FILENAME} \
    --surname_cache_filename=${CRATE_CONTAINER_SURNAME_CACHE_FILENAME} \
    --postcode_cache_filename=${CRATE_CONTAINER_POSTCODE_CACHE_FILENAME} \
    $*"
