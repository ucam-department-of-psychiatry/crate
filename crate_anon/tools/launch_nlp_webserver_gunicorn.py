#!/usr/bin/env python

"""
crate_anon/tools/launch_nlp_webserver_gunicorn.py

===============================================================================

    Copyright (C) 2015-2020 Rudolf Cardinal (rudolf@pobox.com).

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

**Launch CRATE NLP web server via Gunicorn.**

"""

import argparse
import os
import platform
import subprocess
import sys

from crate_anon.nlp_webserver.constants import NLP_WEBSERVER_CONFIG_ENVVAR

WINDOWS = platform.system() == 'Windows'


def main() -> None:
    """
    Command-line parser. See command-line help.
    """
    parser = argparse.ArgumentParser(
        description="Launch CRATE NLP web server via Gunicorn."
                    " (Any leftover arguments will be passed to Gunicorn.)"
    )
    parser.add_argument(
        "--crate_config", default=os.getenv(NLP_WEBSERVER_CONFIG_ENVVAR),
        help=f"CRATE NLP web server config file (default is read from "
             f"environment variable {NLP_WEBSERVER_CONFIG_ENVVAR})"
    )
    args, leftovers = parser.parse_known_args()

    if WINDOWS:
        print("Gunicorn will not run under Windows.")
        sys.exit(1)

    cmdargs = [
        "gunicorn",
        "--paste", args.crate_config,
    ] + leftovers
    cmdargs += leftovers
    print(f"Launching Gunicorn: {cmdargs}")
    subprocess.call(cmdargs)


if __name__ == '__main__':
    main()
