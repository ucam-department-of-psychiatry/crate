#!/usr/bin/env bash

# installer/example_scripts/nlp_BIOMARKERS_FULL.sh

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

# Example script to run full "biomarkers" NLP on an anonymised database.

set -euo pipefail

THISDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
# shellcheck source-path=SCRIPTDIR source=set_crate_environment_vars
source "${THISDIR}"/set_crate_environment_vars

# -- REMOVE ONCE CONFIGURED CORRECTLY
echo "Before using this script, please:"
echo "1. Run ${THISDIR}/generate_nlp_config.sh > ${CRATE_HOST_CONFIG_DIR}/crate_nlp_config.ini"
echo "2. Modify the config file for your setup. See https://crateanon.readthedocs.io/en/latest/nlp/nlp_config.html"
echo "3. Remove these lines from the script"
exit 0
# -- REMOVE TO HERE

${PYTHON} "${CRATE_HOST_INSTALLER_BASE_DIR}/installer.py" exec "crate_nlp_multiprocess \
    --nproc ${CRATE_NPROCESSORS} \
    --config ${CRATE_CONTAINER_CONFIG_NLP} \
    --nlpdef crate_biomarkers \
    --full" \
    2>&1 \
    | tee "${CRATE_HOST_NLP_BIOMARKERS_LOG}"

"${THISDIR}"/email_rdbm.sh --subject "NLP finished" --text "FINISHED: CRATE biomarkers / full"
