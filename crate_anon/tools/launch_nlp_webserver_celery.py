#!/usr/bin/env python

"""
crate_anon/tools/launch_nlp_webserver_celery.py

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

**Launch CRATE NLP web server Celery processes.**

Compare crate_anon/tools/launch_celery.py (for the main CRATE web site).

"""

import argparse
import os
import platform

from cardinal_pythonlib.process import nice_call

from crate_anon.nlp_webserver.tasks import NLP_WEBSERVER_CELERY_APP_NAME


THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DJANGO_ROOT = os.path.abspath(os.path.join(THIS_DIR, os.pardir, "crateweb"))
WINDOWS = platform.system() == 'Windows'


def main() -> None:
    """
    Command-line parser. See command-line help.
    """
    parser = argparse.ArgumentParser(
        description="Launch CRATE NLP web server Celery processes. "
                    "(Any leftover arguments will be passed to Celery.)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--command", default="worker",
        help="Celery command"
    )
    parser.add_argument(
        "--cleanup_timeout_s", type=float, default=10.0,
        help="Time to wait when shutting down Celery via Ctrl-C"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Ask Celery to be verbose"
    )
    args, leftovers = parser.parse_known_args()

    cmdargs = [
        "celery",
        args.command,
        "-A", NLP_WEBSERVER_CELERY_APP_NAME,
    ]
    if args.command == "worker":
        cmdargs += ["-l", "debug" if args.debug else "info"]  # --loglevel
        if WINDOWS:
            # See launch_celery.py
            cmdargs += ["--concurrency=1"]
            cmdargs += ["--pool=solo"]
    cmdargs += leftovers
    print(f"Launching Celery: {cmdargs}")
    nice_call(cmdargs, cleanup_timeout=args.cleanup_timeout_s)


if __name__ == '__main__':
    main()
