#!/usr/bin/env python

"""
crate_anon/crateweb/manage.py

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

**Command-line entry point so we can call Django management commands directly
from the command line if we want.**

"""

import logging
import os
import shlex
import sys
from typing import List

import django
from django.core.management import execute_from_command_line

from crate_anon.crateweb.config.constants import CHERRYPY_EXTRA_ARGS_ENV_VAR

log = logging.getLogger(__name__)


os.environ.setdefault("DJANGO_SETTINGS_MODULE",
                      "crate_anon.crateweb.config.settings")

# from crate_anon.crateweb.config.settings import MIDDLEWARE_CLASSES
# print(f"1. MIDDLEWARE_CLASSES: {id(MIDDLEWARE_CLASSES)}")
# print(f"1. MIDDLEWARE_CLASSES: {MIDDLEWARE_CLASSES}")
django.setup()
# from crate_anon.crateweb.config.settings import MIDDLEWARE_CLASSES
# print(f"2. MIDDLEWARE_CLASSES: {id(MIDDLEWARE_CLASSES)}")
# print(f"2. MIDDLEWARE_CLASSES: {MIDDLEWARE_CLASSES}")

# print(f"sys.path: {sys.path}")
# print(f"os.environ['DJANGO_SETTINGS_MODULE']: "
#       f"{os.environ['DJANGO_SETTINGS_MODULE']}")
# print(f"os.environ['{CRATEWEB_CONFIG_ENV_VAR}']: "
#       f"{os.environ[CRATEWEB_CONFIG_ENV_VAR]}")


def main(argv: List[str] = None) -> None:
    """
    Command-line entry point. Calls the Django command-line processor.
    """
    if argv is None:
        argv = sys.argv
    # print(argv)
    execute_from_command_line(argv)


def runserver() -> None:
    """
    Launch the Django development web server. (Not for proper use.)

    Modifies ``argv`` and calls :func:`main`.
    """
    argv = sys.argv[:]  # copy
    argv.insert(1, 'runserver')
    main(argv)


def runcpserver() -> None:
    """
    Launch the CherryPy web server.

    Modifies ``argv`` and calls :func:`main`.
    """
    argv = sys.argv[:]  # copy
    argv.insert(1, 'runcpserver')
    extraargs = shlex.split(os.environ.get(CHERRYPY_EXTRA_ARGS_ENV_VAR, ''))
    # log.critical(extraargs)
    argv.extend(extraargs)
    main(argv)


def fetch_optouts() -> None:
    """
    Fetch details of patients opting out.

    Modifies ``argv`` and calls :func:`main`.
    """
    argv = sys.argv[:]  # copy
    argv.insert(1, 'fetch_optouts')
    extraargs = shlex.split(os.environ.get(CHERRYPY_EXTRA_ARGS_ENV_VAR, ''))
    # log.critical(extraargs)
    argv.extend(extraargs)
    main(argv)


if __name__ == "__main__":
    main()
