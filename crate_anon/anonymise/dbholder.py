"""
crate_anon/anonymise/dbholder.py

===============================================================================

    Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

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
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

===============================================================================

**Database "holder".**

"""

import logging
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy.engine import create_engine
from sqlalchemy.engine.base import Connection
from sqlalchemy.orm.session import sessionmaker, Session
from sqlalchemy.sql.schema import MetaData

if TYPE_CHECKING:
    from crate_anon.anonymise.config import DatabaseSafeConfig

log = logging.getLogger(__name__)


# =============================================================================
# Convenience object
# =============================================================================


class DatabaseHolder:
    """
    Object to represent a connection to a database.
    """

    def __init__(
        self,
        name: str,
        url: str,
        srccfg: "DatabaseSafeConfig" = None,
        with_session: bool = False,
        with_conn: bool = True,
        reflect: bool = True,
        echo: bool = False,
    ) -> None:
        """
        Args:
            name: internal database name
            url: SQLAlchemy URL
            srccfg: :class:`crate_anon.anonymise.config.DatabaseSafeConfig`
            with_session: create an SQLAlchemy Session?
            with_conn: create an SQLAlchemy connection (via an Engine)?
            reflect: read the database structure (when required)?
            echo: passed to SQLAlchemy's :func:`create_engine`
        """
        self.name = name
        self.srccfg = srccfg
        self.engine = create_engine(url, echo=echo, future=True)
        self.conn = None  # type: Optional[Connection]
        self.session = None  # type: Optional[Session]
        self._reflect_on_request = reflect
        self._reflected = False
        self._table_names = []  # type: List[str]
        self._metadata = MetaData()
        log.debug(self.engine)  # obscures password

        if with_conn:  # for raw connections
            self.conn = self.engine.connect()
        if with_session:  # for ORM
            self.create_session()

    def enable_reflect(self) -> None:
        """
        Enables reflection, if it wasn't enabled to begin with.
        """
        self._reflect_on_request = True

    def create_session(self) -> None:
        """
        Creates a database session, if not created to begin with.
        """
        if not self.session:
            self.session = sessionmaker(
                bind=self.engine, future=True
            )()  # type: Session

    def _reflect(self) -> None:
        """
        Perform the database reflection.

        Reflection is expensive, so we defer unless required
        """
        if not self._reflect_on_request:
            return
        log.info(f"Reflecting database: {self.name}")
        # self.table_names = get_table_names(self.engine)
        self._metadata.reflect(bind=self.engine, views=True)  # include views
        self._table_names = [t.name for t in self._metadata.sorted_tables]
        self._reflected = True

    def update_metadata(self) -> None:
        """
        Updates the metadata, for example if a table has been dropped.
        """
        self._metadata = MetaData()

    @property
    def metadata(self) -> MetaData:
        """
        Returns the SQLAlchemy :class:`MetaData`. If reflection is enabled,
        ensure the database has been reflected first.
        """
        if not self._reflected:
            self._reflect()
        return self._metadata

    @property
    def table_names(self) -> List[str]:
        """
        Returns the table names from the database, if reflection is enabled.
        (Otherwise returns an empty list.)
        """
        if not self._reflected:
            self._reflect()
        return self._table_names
