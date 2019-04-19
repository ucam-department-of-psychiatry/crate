#!/usr/bin/env python

r"""
crate_anon/nlp_web/print_demo_config.py

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

Prints a demo config for CRATE's implementation of an NLPRP server.
"""
import argparse
import logging

from crate_anon.nlp_web.constants import DEMO_CONFIG, DEMO_PROCESSORS

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

def main() -> None:
    """
    Command line entry point.
    """
    description = ("Print demo config file or demo processor constants file "
                   "for server side cloud nlp.")
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    arg_group = parser.add_mutually_exclusive_group()
    arg_group.add_argument(
        "--config", action="store_true",
        help="Print a demo config file for server side cloud nlp.")
    arg_group.add_argument(
        "--processors", action="store_true",
        help="Print a demo processor constants file for server side cloud "
             "nlp.")
    args = parser.parse_args()

    if args.config:
        print(DEMO_CONFIG)
    elif args.processors:
        print(DEMO_PROCESSORS)
    else:
        log.error("One option required: '--config' or '--processors'.")
