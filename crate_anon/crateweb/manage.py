#!/usr/bin/env python
# crate_anon/crateweb/manage.py

"""
===============================================================================
    Copyright © 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

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
# print("1. MIDDLEWARE_CLASSES: {}".format(id(MIDDLEWARE_CLASSES)))
# print("1. MIDDLEWARE_CLASSES: {}".format(MIDDLEWARE_CLASSES))
django.setup()
# from crate_anon.crateweb.config.settings import MIDDLEWARE_CLASSES
# print("2. MIDDLEWARE_CLASSES: {}".format(id(MIDDLEWARE_CLASSES)))
# print("2. MIDDLEWARE_CLASSES: {}".format(MIDDLEWARE_CLASSES))

# print("sys.path: {}".format(sys.path))
# print("os.environ['DJANGO_SETTINGS_MODULE']: {}".format(
#     os.environ['DJANGO_SETTINGS_MODULE']))
# print("os.environ['{}']: {}".format(
#     CRATEWEB_CONFIG_ENV_VAR, os.environ[CRATEWEB_CONFIG_ENV_VAR]))


def main(argv: List[str] = None) -> None:
    if argv is None:
        argv = sys.argv
    # print(argv)
    execute_from_command_line(argv)


def runserver() -> None:
    argv = sys.argv[:]  # copy
    argv.insert(1, 'runserver')
    main(argv)


def runcpserver() -> None:
    argv = sys.argv[:]  # copy
    argv.insert(1, 'runcpserver')
    extraargs = shlex.split(os.environ.get(CHERRYPY_EXTRA_ARGS_ENV_VAR, ''))
    # log.critical(extraargs)
    argv.extend(extraargs)
    main(argv)


if __name__ == "__main__":
    main()
