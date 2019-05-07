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

# from crate_anon.nlp_web.constants import DEMO_CONFIG, DEMO_PROCESSORS

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

# We need to do this here rather than in constants because otherwise it tries
# to get the settings file before it's been created
DEMO_CONFIG = """
[app:main]
use = egg:crate_anon
pyramid.reload_templates = true
# pyramid.includes =
#     pyramid_debugtoolbar
nlp_web.secret = changethis
sqlalchemy.url = mysql://username:password@localhost/dbname?charset=utf8

# Absolute path of users file
users_file = /home/.../nlp_web_files/users.txt

# Absolute path of processors file - this must be a .py file in the correct
# format
processors_path = /home/.../nlp_web_files/processor_constants.py

# urls for queueing
broker_url = amqp://@localhost:3306/testbroker
backend_url = db+mysql://username:password@localhost/backenddbname?charset=utf8

# Key for reversible encryption. Use 'nlp_web_generate_encryption_key'.
encryption_key =

[server:main]
use = egg:waitress#main
listen = localhost:6543
"""


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
        from crate_anon.nlp_web.constants import DEMO_PROCESSORS
        print(DEMO_PROCESSORS)
    else:
        log.error("One option required: '--config' or '--processors'.")
