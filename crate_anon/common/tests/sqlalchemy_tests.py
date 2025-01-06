"""
crate_anon/common/tests/sqlalchemy_tests.py

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

Unit testing.

"""

# =============================================================================
# Imports
# =============================================================================

import logging
from unittest import TestCase

from sqlalchemy import Column, String, Integer, create_engine
from sqlalchemy.dialects.mysql.base import MySQLDialect
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm.session import Session
from sqlalchemy.exc import IntegrityError

from crate_anon.common.sqlalchemy import insert_with_upsert_if_supported

log = logging.getLogger(__name__)


# =============================================================================
# Unit tests
# =============================================================================


class SqlAlchemyTests(TestCase):

    def test_insert_with_upsert_if_supported_syntax(self) -> None:
        # noinspection PyPep8Naming
        Base = declarative_base()

        class OrmObject(Base):
            __tablename__ = "sometable"
            id = Column(Integer, primary_key=True)
            name = Column(String)

        sqlite_engine = create_engine("sqlite://", echo=True, future=True)
        Base.metadata.create_all(sqlite_engine)

        session = Session(sqlite_engine)

        d1 = dict(id=1, name="One")
        d2 = dict(id=2, name="Two")

        table = OrmObject.__table__

        insert_1 = table.insert().values(d1)
        insert_2 = table.insert().values(d2)
        session.execute(insert_1)
        session.execute(insert_2)
        with self.assertRaises(IntegrityError):
            session.execute(insert_1)

        upsert_1 = insert_with_upsert_if_supported(
            table=table, values=d1, session=session
        )
        odku = "ON DUPLICATE KEY UPDATE"
        self.assertFalse(odku in str(upsert_1))

        upsert_2 = insert_with_upsert_if_supported(
            table=table, values=d1, dialect=MySQLDialect()
        )
        self.assertTrue(odku in str(upsert_2))

        # We can't test fully here without a MySQL connection.
        # But syntax tested separately in upsert_test_1.sql
