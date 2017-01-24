#!/usr/bin/env python
# crate_anon/anonymise/test_extract_text.py

"""
===============================================================================
    Copyright (C) 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

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
import sys

from cardinal_pythonlib.rnc_extract_text import document_to_text


def uprint(*objects, sep=' ', end='\n', file=sys.stdout):
    # http://stackoverflow.com/questions/14630288/unicodeencodeerror-charmap-codec-cant-encode-character-maps-to-undefined  # noqa
    enc = file.encoding
    if enc == 'UTF-8':
        print(*objects, sep=sep, end=end, file=file)
    else:
        def f(obj):
            return str(obj).encode(enc, errors='backslashreplace').decode(enc)
        print(*map(f, objects), sep=sep, end=end, file=file)


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
    result = document_to_text(filename=args.filename,
                              blob=None,
                              extension=extension,
                              plain=args.plain,
                              width=args.width)
    uprint(result)


if __name__ == '__main__':
    main()
