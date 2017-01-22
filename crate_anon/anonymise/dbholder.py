#!/usr/bin/env python
# crate_anon/anonymise/dbholder.py

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

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import MetaData

# from crate_anon.common.sqla import get_table_names

log = logging.getLogger(__name__)


# =============================================================================
# Convenience object
# =============================================================================

DB_SAFE_CONFIG_FWD_REF = "DatabaseSafeConfig"


class DatabaseHolder(object):
    def __init__(self,
                 name: str,
                 url: str,
                 srccfg: DB_SAFE_CONFIG_FWD_REF = None,
                 with_session: bool = False,
                 with_conn: bool = True,
                 reflect: bool = True,
                 encoding: str = 'utf-8') -> None:
        self.name = name
        self.srccfg = srccfg
        self.engine = create_engine(url, encoding=encoding)
        self.conn = None
        self.session = None
        self.table_names = []
        self.metadata = MetaData(bind=self.engine)
        log.debug(self.engine)  # obscures password

        if with_conn:  # for raw connections
            self.conn = self.engine.connect()
        if reflect:
            # self.table_names = get_table_names(self.engine)
            self.metadata.reflect(views=True)  # include views
            self.table_names = [t.name
                                for t in self.metadata.sorted_tables]
        if with_session:  # for ORM
            self.session = sessionmaker(bind=self.engine)()  # for ORM

