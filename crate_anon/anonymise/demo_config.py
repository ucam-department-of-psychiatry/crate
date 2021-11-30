#!/usr/bin/env python

"""
crate_anon/anonymise/demo_config.py

===============================================================================

    Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).

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

**Print a demonstration config file for the anonymiser.**

"""

import argparse

from cardinal_pythonlib.file_io import smart_open

from crate_anon.anonymise.constants import DEMO_CONFIG
from crate_anon.version import CRATE_VERSION_PRETTY


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    """
    Command-line entry point.
    """
    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(
        description=f"Print a demo config file for the CRATE anonymiser. "
                    f"({CRATE_VERSION_PRETTY})",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument(
        "--output", default="-",
        help="File for output; use '-' for stdout.")

    args = parser.parse_args()

    # -------------------------------------------------------------------------
    # Print demo config
    # -------------------------------------------------------------------------

    with smart_open(args.output, "w") as f:
        print(DEMO_CONFIG, file=f)
