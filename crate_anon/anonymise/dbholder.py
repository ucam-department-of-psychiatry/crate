#!/usr/bin/env python

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import MetaData

from crate_anon.anonymise.sqla import get_table_names

log = logging.getLogger(__name__)


# =============================================================================
# Convenience object
# =============================================================================

class DatabaseHolder(object):
    def __init__(self, name, url, srccfg=None, with_session=False,
                 with_conn=True, reflect=True, encoding='utf-8'):
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
            self.table_names = get_table_names(self.engine)
            self.metadata.reflect()
            self.table_names = [t.name
                                for t in self.metadata.sorted_tables]
        if with_session:  # for ORM
            self.session = sessionmaker(bind=self.engine)()  # for ORM

