"""
crate_anon/version.py

===============================================================================

    Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

    This file is part of CRATE.

    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

===============================================================================

**Version constants for CRATE.**

"""

import sys


# =============================================================================
# Constants
# =============================================================================

CRATE_VERSION = "0.20.7"
CRATE_VERSION_DATE = "2025-05-05"

MINIMUM_PYTHON_VERSION = (3, 9)
# Only other place that has this: install_virtualenv.py (which can't import
# CRATE packages).


# =============================================================================
# Derived constants
# =============================================================================

CRATE_VERSION_PRETTY = (
    f"CRATE version {CRATE_VERSION}, {CRATE_VERSION_DATE}. "
    f"Created by Rudolf Cardinal."
)
MINIMUM_PYTHON_VERSION_AS_DECIMAL = ".".join(
    str(_) for _ in MINIMUM_PYTHON_VERSION
)


# =============================================================================
# Helper functions
# =============================================================================


def require_minimum_python_version():
    """
    Checks that we are running the required minimum Python version.
    """
    assert (
        sys.version_info >= MINIMUM_PYTHON_VERSION
    ), f"Need Python {MINIMUM_PYTHON_VERSION_AS_DECIMAL}+"
