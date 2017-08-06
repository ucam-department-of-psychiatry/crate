#!/usr/bin/env python
# crate_anon/tools/merge_csv.py

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
import csv
import logging
import sys
from typing import List, TextIO

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger

log = logging.getLogger(__name__)


def merge_csv(filenames: List[str],
              outfile: TextIO = sys.stdout,
              input_dialect: str = 'excel',
              output_dialect: str = 'excel',
              debug: bool = False,
              headers: bool = True) -> None:
    writer = csv.writer(outfile, dialect=output_dialect)
    written_header = False
    header_items = []  # type: List(str)
    for filename in filenames:
        log.info("Processing file " + repr(filename))
        with open(filename, 'r') as f:
            reader = csv.reader(f, dialect=input_dialect)
            if headers:
                if not written_header:
                    header_items = next(reader)
                    if debug:
                        log.debug("Header row: {}".format(repr(header_items)))
                    writer.writerow(header_items)
                    written_header = True
                else:
                    new_headers = next(reader)
                    if new_headers != header_items:
                        raise ValueError(
                            "Header line in file {filename} doesn't match - "
                            "it was {new} but previous was {old}".format(
                                filename=repr(filename),
                                new=repr(new_headers),
                                old=repr(header_items),
                            ))
                    if debug:
                        log.debug("Header row matches previous")
            else:
                if debug:
                    log.debug("No headers in use")
            for row in reader:
                if debug:
                    log.debug("Data row: {}".format(repr(row)))
                writer.writerow(row)


def main():
    main_only_quicksetup_rootlogger()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "filenames",
        nargs="+",
        help="Names of CSV/TSV files to merge"
    )
    parser.add_argument(
        "--outfile",
        default="-",
        help="Specify an output filename. If omitted or '-', stdout is used.",
    )
    parser.add_argument(
        "--inputdialect",
        default="excel",
        help="The input files' CSV/TSV dialect. Default: %(default)s.",
        choices=csv.list_dialects(),
    )
    parser.add_argument(
        "--outputdialect",
        default="excel",
        help="The output file's CSV/TSV dialect. Default: %(default)s.",
        choices=csv.list_dialects(),
    )
    parser.add_argument(
        "--noheaders",
        action="store_true",
        help="By default, files are assumed to have column headers. "
             "Specify this option to assume no headers.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Verbose debugging output.",
    )
    progargs = parser.parse_args()

    kwargs = {
        "filenames": progargs.filenames,
        "input_dialect": progargs.inputdialect,
        "output_dialect": progargs.outputdialect,
        "debug": progargs.debug,
        "headers": not progargs.noheaders,
    }
    if progargs.outfile == '-':
        log.info("Writing to stdout")
        merge_csv(outfile=sys.stdout, **kwargs)
    else:
        log.info("Writing to " + repr(progargs.outfile))
        with open(progargs.outfile, 'w') as outfile:
            # noinspection PyTypeChecker
            merge_csv(outfile=outfile, **kwargs)


if __name__ == '__main__':
    main()
