#!/usr/bin/env python
# tools/list_all_extensions.py

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
"""

import argparse
import logging
import os
from typing import List

log = logging.getLogger(__name__)


def list_file_extensions(path: str, reportevery: int = 1) -> List[str]:
    extensions = set()
    count = 0
    for root, dirs, files in os.walk(path):
        count += 1
        if count % reportevery == 0:
            log.debug("Walking directory {}: {}".format(count, repr(root)))
        for file in files:
            filename, ext = os.path.splitext(file)
            extensions.add(ext)
    return sorted(list(extensions))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", nargs="?", default=os.getcwd())
    parser.add_argument("--reportevery", default=10000)
    args = parser.parse_args()
    log.info("Extensions in directory {}:".format(repr(args.directory)))
    print("\n".join(list_file_extensions(args.directory,
                                         reportevery=args.reportevery)))


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
