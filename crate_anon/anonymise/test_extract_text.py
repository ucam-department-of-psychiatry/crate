#!/usr/bin/env python
# crate_anon/anonymise/test_extract_text.py

"""
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

Anonymise multiple SQL-based databases using a data dictionary.

"""

import argparse
import os

from cardinal_pythonlib.extract_text import (
    document_to_text,
    TextProcessingConfig,
)

from crate_anon.common.stringfunc import uprint


def main():
    parser = argparse.ArgumentParser(
        description="Test CRATE text extraction",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('filename', type=str,
                        help="File from which to extract text")
    parser.add_argument('--plain', action='store_true',
                        help="Use plainest format (not e.g. table layouts)")
    parser.add_argument('--width', type=int, default=80,
                        help="Width to word-wrap to")

    args = parser.parse_args()

    extension = os.path.splitext(args.filename)[1]
    config = TextProcessingConfig(
        plain=args.plain,
        width=args.width
    )
    result = document_to_text(filename=args.filename,
                              blob=None,
                              extension=extension,
                              config=config)
    uprint(result)


if __name__ == '__main__':
    main()
