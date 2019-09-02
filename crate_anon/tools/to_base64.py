#!/usr/bin/env python

"""
crate_anon/tools/to_base64.py

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

**Write a file as base64 to stdout.**

"""

import argparse
import base64
import logging
import re
import sys


log = logging.getLogger(__name__)

RE_WHITESPACE = re.compile(r"[ \n\t]+")


def main() -> None:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "filename", type=str,
        help="Filename to read"
    )
    parser.add_argument(
        "--as_text", action="store_true",
        help="Read the file as text, not binary"
    )
    tg = parser.add_argument_group("For text")
    tg.add_argument(
        "--encoding", type=str, default=sys.getdefaultencoding(),
        help="Encoding to use for reading text"
    )
    tg.add_argument(
        "--strip_whitespace", action="store_true",
        help="Replace spaces/newlines with single spaces"
    )
    args = parser.parse_args()

    if args.as_text:
        with open(args.filename, "rt", encoding=args.encoding) as f:
            text = f.read()  # type: str
            log.debug(f"Start: \n{text}")
            if args.strip_whitespace:
                text = " ".join(RE_WHITESPACE.split(text))
                log.debug(f"Converted to: \n{text}")
            data = text.encode(args.encoding)
    else:
        with open(args.filename, "rb") as f:
            data = f.read()  # type: bytes
    log.info("Base64-encoded version is:")
    encoded = base64.b64encode(data)  # type: bytes
    print(encoded.decode("ascii"))


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
