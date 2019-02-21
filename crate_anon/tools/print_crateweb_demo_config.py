#!/usr/bin/env python

"""
crate_anon/tools/print_crateweb_demo_config.py

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

**Print a demonstration CRATE web (Django) config file.**

"""

import os


def main():
    """
    Command-line entry point.
    """
    this_dir = os.path.abspath(os.path.dirname(__file__))
    filename = os.path.abspath(os.path.join(
        this_dir, "..", "crateweb", "specimen_secret_local_settings",
        "crateweb_local_settings.py"
    ))
    for line in open(filename):
        print(line.rstrip('\n'))


if __name__ == '__main__':
    main()
