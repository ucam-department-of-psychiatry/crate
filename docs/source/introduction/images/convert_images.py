#!/usr/bin/env python

"""
docs/source/introduction/images/convert_images.py

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

**Convert images for the documentation.**

"""

import subprocess
import os

FILENAMES = ['crate.pdf']
THIS_DIR = os.path.dirname(os.path.realpath(__file__))


if __name__ == "__main__":
    for filename in FILENAMES:
        infile = os.path.join(THIS_DIR, filename)
        outfile = os.path.splitext(infile)[0] + '.png'
        args = ['convert', '-trim', '-density', '300', infile, outfile]
        subprocess.call(args)
