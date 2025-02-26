#!/usr/bin/env bash

# installer/example_scripts/load_ons_postcode_database.sh

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

# Example script to load the Office of National Statistics Postcode Database
# from spreadsheet files to a database specified by CRATE_ONSPD_URL

set -euo pipefail

THISDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
# shellcheck source-path=SCRIPTDIR source=set_crate_environment_vars
source "${THISDIR}"/set_crate_environment_vars

# -- REMOVE ONCE CONFIGURED CORRECTLY
echo "Before using this script, please:"
echo "1. Download and extract a copy of ONSPD from e.g. https://geoportal.statistics.gov.uk/search?q=PRD_ONSPD%20NOV_2024 into ${CRATE_HOST_ONSPD_DIR}"
echo "2. Create an empty database and set CRATE_ONSPD URL in set_crate_environment_vars to point to it."
echo "3. Remove these lines from the script"
exit 0
# -- REMOVE TO HERE

${PYTHON} "${CRATE_HOST_INSTALLER_BASE_DIR}/installer.py" exec "crate_postcodes \
    --dir ${CRATE_HOST_ONSPD_DIR}/ \
    --url ${CRATE_ONSPD_URL}"
