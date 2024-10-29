#!/bin/bash

# installer/start_crate.sh

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

# Starts CRATE

set -euo pipefail

PYTHON=${CRATE_INSTALLER_CRATE_ROOT_HOST_DIR}/venv/bin/python

# Restore user's environment variables, if found
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
source "${SCRIPT_DIR}/restore_crate_envvars.sh"

# Run Python installer script with a command
INSTALLER_HOME="$( cd "$( dirname "$0" )" && pwd )"
${PYTHON} "${INSTALLER_HOME}/installer.py" start
