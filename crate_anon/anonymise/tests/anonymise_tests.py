#!/usr/bin/env python

"""
crate_anon/anonymise/tests/anonymise_tests.py

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

"""

import factory
from unittest import mock

from sqlalchemy import (
    Boolean,
    Column,
    Integer,
)

from crate_anon.testing.classes import Base, BaseFactory, DatabaseTestCase
from crate_anon.anonymise.anonymise import gen_opt_out_pids_from_database


class TestOptOut(Base):
    __tablename__ = "test_opt_out"

    pid = Column(Integer, primary_key=True, comment="Patient ID")
    mpid = Column(Integer, comment="Master patient ID")
    opt_out = Column(Boolean, comment="Opt out?")


class TestOptOutFactory(BaseFactory):
    class Meta:
        model = TestOptOut

    pid = factory.Sequence(lambda n: n)
    mpid = factory.Sequence(lambda n: n)


class GenOptOutPidsFromDatabaseTests(DatabaseTestCase):
    def test_string_in_optout_col_values_ignored_for_boolean_column(
        self,
    ) -> None:
        optout_defining_fields = mock.Mock(
            return_value=[
                (
                    "db",
                    "test_opt_out",
                    "opt_out",
                    "pid",
                    "mpid",
                )
            ]
        )
        mock_dd = mock.Mock(get_optout_defining_fields=optout_defining_fields)
        mock_sources = {
            "db": mock.Mock(session=self.dbsession),
        }

        oo_1 = TestOptOutFactory(opt_out=True)
        oo_2 = TestOptOutFactory(opt_out=True)
        oo_3 = TestOptOutFactory(opt_out=True)
        oo_4 = TestOptOutFactory(opt_out=False)
        self.dbsession.flush()

        with mock.patch.multiple(
            "crate_anon.anonymise.anonymise.config",
            dd=mock_dd,
            sources=mock_sources,
            optout_col_values=[True, 1, "1"],
        ):
            pids = list(gen_opt_out_pids_from_database())

            self.assertIn(oo_1.pid, pids)
            self.assertIn(oo_2.pid, pids)
            self.assertIn(oo_3.pid, pids)
            self.assertNotIn(oo_4.pid, pids)
