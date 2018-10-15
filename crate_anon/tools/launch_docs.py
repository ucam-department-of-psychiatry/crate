#!/usr/bin/env python
# crate_anon/tools/launch_docs.py

"""
..

===============================================================================

    Copyright (C) 2015-2018 Rudolf Cardinal (rudolf@pobox.com).

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


# THIS_DIR = os.path.abspath(os.path.dirname(__file__))
# DOCS_INDEX = os.path.abspath(os.path.join(
#     THIS_DIR,  # crate_anon/tools
#     os.pardir,  # crate_anon
#     "docs",
#     "build",
#     "html",
#     "index.html"
# ))

DOCS_INDEX = "https://crateanon.readthedocs.io/"


def main():
    """
    Command-line entry point.
    """
    print("Launching help: {}".format(DOCS_INDEX))
    launch_external_file(DOCS_INDEX)


if __name__ == '__main__':
    main()
