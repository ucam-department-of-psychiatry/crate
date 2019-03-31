#!/usr/bin/env python

r"""
crate_anon/nlp_web/initialize_db.py

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

Tool to initialize the database used by CRATE's implementation of an NLPRP
server.

"""

import os
import sys
from typing import List

from sqlalchemy import engine_from_config
from pyramid.paster import get_appsettings

from crate_anon.nlp_web.models import DBSession, Base


def usage(argv: List[str]) -> None:
    """
    Prints program usage to stdout and quits with an error code.
    """
    cmd = os.path.basename(argv[0])
    print('usage: %s <config_uri>\n'
          '(example: "%s development.ini")' % (cmd, cmd))
    sys.exit(1)


def main(argv: List[str] = sys.argv) -> None:
    """
    Command-line entry point.
    """
    if len(argv) != 2:
        usage(argv)
    config_uri = argv[1]
    # setup_logging(config_uri)
    settings = get_appsettings(config_uri)
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    Base.metadata.create_all(engine)
