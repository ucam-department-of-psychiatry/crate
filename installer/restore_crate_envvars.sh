# installer/restore_crate_envvars.sh

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

# When the installer first runs, it stores a copy of the relevant environment
# variables. To run other Docker commands, it's helpful to "source" them back,
# if found. Likewise, this file itself should be "sourced", not executed.

# The default is $HOME/crate/set_crate_docker_host_envvars (per HostPath in
# installer.py). We allow the user to pre-override this with environment
# variables.
CRATE_DIR=${CRATE_DIR:=$HOME/crate}
CRATE_CONFIG_DIR=${CRATE_CONFIG_DIR:=$CRATE_DIR/config}
CRATE_ENVVAR_FILE=${CRATE_CONFIG_DIR}/set_crate_docker_host_envvars
# ... filename itself not configurable, and written by installer.py

if [ -f "${CRATE_ENVVAR_FILE}" ]; then
    echo "- Restoring user-supplied environment variables from: ${CRATE_ENVVAR_FILE}"
    # shellcheck disable=SC1090
    source "${CRATE_ENVVAR_FILE}"
else
    echo "- No previous environment variable file found at: ${CRATE_ENVVAR_FILE}"
fi
