#!/usr/bin/env python

"""
crate_anon/anonymise/test_extract_text.py

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

**Test CRATE's text-extraction system.**

"""

import argparse
import os
import sys
import traceback

from cardinal_pythonlib.argparse_func import (
    RawDescriptionArgumentDefaultsHelpFormatter,
)
from cardinal_pythonlib.extract_text import (
    document_to_text,
    TextProcessingConfig,
)

from crate_anon.common.stringfunc import uprint

EXIT_TEXT = 0
EXIT_NO_TEXT = 1
EXIT_ERROR = 2


def main() -> int:
    """
    Command-line entry point. See command-line help.
    """
    parser = argparse.ArgumentParser(
        description=f"""
Test CRATE text extraction and/or detect text in files.

Exit codes:
- {EXIT_TEXT} for "text found"
- {EXIT_NO_TEXT} for "no text found"
- {EXIT_ERROR} for "error" (e.g. file not found)
        """,
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter)
    parser.add_argument('filename', type=str,
                        help="File from which to extract text")
    parser.add_argument('--plain', action='store_true',
                        help="Use plainest format (not e.g. table layouts)")
    parser.add_argument('--width', type=int, default=80,
                        help="Width to word-wrap to")
    parser.add_argument('--silent', action="store_true",
                        help="Don't print the text, just exit with a code")

    args = parser.parse_args()

    extension = os.path.splitext(args.filename)[1]
    config = TextProcessingConfig(
        plain=args.plain,
        width=args.width
    )
    # noinspection PyBroadException
    try:
        result = document_to_text(filename=args.filename,
                                  blob=None,
                                  extension=extension,
                                  config=config)
    except Exception:
        traceback.print_exc(file=sys.stderr)  # full details, please
        return EXIT_ERROR

    contains_text = bool(result.strip())
    if not args.silent:
        uprint(result)
    return EXIT_TEXT if contains_text else EXIT_NO_TEXT


if __name__ == '__main__':
    sys.exit(main())
