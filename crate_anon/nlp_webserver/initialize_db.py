#!/usr/bin/env python

r"""
crate_anon/nlp_webserver/initialize_db.py

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

import argparse
import logging

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from cardinal_pythonlib.sqlalchemy.session import get_safe_url_from_engine
from sqlalchemy import engine_from_config
from pyramid.paster import get_appsettings

from crate_anon.nlp_webserver.constants import NlpServerConfigKeys
from crate_anon.nlp_webserver.models import dbsession, Base

log = logging.getLogger(__name__)


def main() -> None:
    """
    Command-line entry point.
    """
    parser = argparse.ArgumentParser(
        description="Tool to initialize the database used by CRATE's "
                    "implementation of an NLPRP server."
    )
    parser.add_argument(
        "config_uri", type=str,
        help="Config file to read (e.g. 'development.ini'); URL of database "
             "is found here."
    )
    args = parser.parse_args()
    main_only_quicksetup_rootlogger()

    config_file = args.config_uri
    log.debug(f"Settings file: {config_file}")
    settings = get_appsettings(config_file)
    engine = engine_from_config(settings,
                                NlpServerConfigKeys.SQLALCHEMY_PREFIX)
    sqla_url = get_safe_url_from_engine(engine)
    log.info(f"Using database {sqla_url!r}")
    dbsession.configure(bind=engine)
    log.info("Creating database structure...")
    Base.metadata.create_all(engine)
    log.info("... done.")


if __name__ == "__main__":
    main()
