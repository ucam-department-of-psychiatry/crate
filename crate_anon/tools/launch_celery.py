#!/usr/bin/env python

"""
crate_anon/tools/launch_celery.py

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

**Launch CRATE Celery processes.**

"""

import argparse
import os
import platform

from cardinal_pythonlib.process import nice_call

from crate_anon.crateweb.config.constants import CRATEWEB_CELERY_APP_NAME


THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DJANGO_ROOT = os.path.abspath(os.path.join(THIS_DIR, os.pardir, "crateweb"))
WINDOWS = platform.system() == 'Windows'


# http://stackoverflow.com/questions/21666229/celery-auto-reload-on-any-changes
# HOWEVER: autoreload appears (a) not to work, and (b) to prevent processing!


def main() -> None:
    """
    Command-line parser. See command-line help.
    """
    parser = argparse.ArgumentParser(
        description="Launch CRATE Celery processes. "
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

    # print(f"Changing to directory: {DJANGO_ROOT}")
    # os.chdir(DJANGO_ROOT)
    cmdargs = [
        "celery",
        args.command,
        "-A", CRATEWEB_CELERY_APP_NAME,
    ]
    if args.command == "worker":
        cmdargs += ["-l", "debug" if args.debug else "info"]  # --loglevel
        if WINDOWS:
            # Default concurrency is 1. Under Celery 3.1.23, RabbitMQ 3.6.1,
            # and Windows 10, things like "celery -A myapp status" don't work
            # unless the concurrency flag is increased, e.g. to 4.
            # (Default is 1 under Windows.)
            # cmdargs += ["--concurrency=4"]
            cmdargs += ["--concurrency=1"]  # 2018-06-29

            # Without "--pool=solo", sod all happens: tasks go into the
            # Reserved queue, but aren't executed.
            # See:
            # http://docs.celeryproject.org/en/latest/reference/celery.bin.worker.html#module-celery.bin.worker  # noqa
            # https://github.com/celery/celery/issues/2146
            cmdargs += ["--pool=solo"]

            # The "-Ofair" option is relevant to pre-fetching, but doesn't
            # seem critical.
            # cmdargs += ["-Ofair"]

        # We don't need to specify modules manually, now we have a package.
        # modules = get_python_modules(DJANGO_ROOT,
        #                              prefix="crate_anon.crateweb.")
        # cmdargs += ["--include", f"{','.join(modules)}"]

        # "--autoreload",
    cmdargs += leftovers
    print(f"Launching Celery: {cmdargs}")
    nice_call(cmdargs, cleanup_timeout=args.cleanup_timeout_s)


if __name__ == '__main__':
    main()
