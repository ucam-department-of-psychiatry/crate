#!/usr/bin/env python

"""
crate_anon/tools/launch_docs.py

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

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
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.

===============================================================================

**Launch the CRATE docs.**

"""

from cardinal_pythonlib.process import launch_external_file

from crate_anon.common.constants import CRATE_DOCS_URL


def main():
    """
    Command-line entry point.
    """
    print(f"Launching help: {CRATE_DOCS_URL}")
    launch_external_file(CRATE_DOCS_URL)


if __name__ == '__main__':
    main()
