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

import logging
from unittest import mock

import factory
from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    String,
)

from crate_anon.testing.classes import Base, BaseFactory, DatabaseTestCase
from crate_anon.anonymise.anonymise import (
    gen_opt_out_pids_from_database,
    validate_optouts,
)


class TestBoolOptOut(Base):
    __tablename__ = "test_opt_out_bool"

    pid = Column(Integer, primary_key=True, comment="Patient ID")
    mpid = Column(Integer, comment="Master patient ID")
    opt_out = Column(Boolean, comment="Opt out?")


class TestBoolOptOutFactory(BaseFactory):
    class Meta:
        model = TestBoolOptOut

    pid = factory.Sequence(lambda n: n + 1)
    mpid = factory.Sequence(lambda n: n + 1)


class TestStringOptOut(Base):
    __tablename__ = "test_opt_out_string"

    pid = Column(Integer, primary_key=True, comment="Patient ID")
    mpid = Column(Integer, comment="Master patient ID")
    opt_out = Column(String(4), comment="Opt out?")


class TestStringOptOutFactory(BaseFactory):
    class Meta:
        model = TestStringOptOut

    pid = factory.Sequence(lambda n: n + 1)
    mpid = factory.Sequence(lambda n: n + 1)


class GenOptOutPidsFromDatabaseTests(DatabaseTestCase):
    def test_string_in_optout_col_values_ignored_for_boolean_column(
        self,
    ) -> None:
        optout_defining_fields = mock.Mock(
            return_value=[
                (
                    "db",
                    "test_opt_out_bool",
                    "opt_out",
                    "pid",
                    "mpid",
                )
            ]
        )
        mock_dd = mock.Mock(get_optout_defining_fields=optout_defining_fields)
        mock_sources = {
            "db": mock.Mock(
                session=self.dbsession,
                engine=self.engine,
                metadata=Base.metadata,
            ),
        }

        opt_out_1 = TestBoolOptOutFactory(opt_out=True)
        opt_out_2 = TestBoolOptOutFactory(opt_out=True)
        opt_out_3 = TestBoolOptOutFactory(opt_out=True)
        opt_out_4 = TestBoolOptOutFactory(opt_out=False)
        self.dbsession.flush()

        with mock.patch.multiple(
            "crate_anon.anonymise.anonymise.config",
            dd=mock_dd,
            sources=mock_sources,
            optout_col_values=[True, 1, "1"],
        ):
            pids = list(gen_opt_out_pids_from_database())

            self.assertIn(opt_out_1.pid, pids)
            self.assertIn(opt_out_2.pid, pids)
            self.assertIn(opt_out_3.pid, pids)
            self.assertNotIn(opt_out_4.pid, pids)

    def test_invalid_boolean_optout_col_value_logged(
        self,
    ) -> None:
        optout_defining_fields = mock.Mock(
            return_value=[
                (
                    "db",
                    "test_opt_out_bool",
                    "opt_out",
                    "pid",
                    "mpid",
                )
            ]
        )
        mock_dd = mock.Mock(get_optout_defining_fields=optout_defining_fields)
        mock_sources = {
            "db": mock.Mock(
                session=self.dbsession,
                engine=self.engine,
                metadata=Base.metadata,
            ),
        }

        TestBoolOptOutFactory(opt_out=True)
        self.dbsession.flush()

        with mock.patch.multiple(
            "crate_anon.anonymise.anonymise.config",
            dd=mock_dd,
            sources=mock_sources,
            optout_col_values=["1"],
        ):
            with self.assertLogs(level=logging.INFO) as logging_cm:
                list(gen_opt_out_pids_from_database())

                logger_name = "crate_anon.anonymise.anonymise"
                expected_message = (
                    "... ignoring non-boolean value (1), type 'str' "
                    "for boolean column 'opt_out'"
                )
                self.assertIn(
                    f"INFO:{logger_name}:{expected_message}", logging_cm.output
                )

    def test_string_in_optout_col_values_valid_for_string_column(
        self,
    ) -> None:
        optout_defining_fields = mock.Mock(
            return_value=[
                (
                    "db",
                    "test_opt_out_string",
                    "opt_out",
                    "pid",
                    "mpid",
                )
            ]
        )
        mock_dd = mock.Mock(get_optout_defining_fields=optout_defining_fields)
        mock_sources = {
            "db": mock.Mock(
                session=self.dbsession,
                engine=self.engine,
                metadata=Base.metadata,
            ),
        }

        opt_out_1 = TestStringOptOutFactory(opt_out="yes")
        opt_out_2 = TestStringOptOutFactory(opt_out="1")
        opt_out_3 = TestStringOptOutFactory(opt_out="no")
        opt_out_4 = TestStringOptOutFactory(opt_out="0")
        self.dbsession.flush()

        with mock.patch.multiple(
            "crate_anon.anonymise.anonymise.config",
            dd=mock_dd,
            sources=mock_sources,
            optout_col_values=["yes", "1"],
        ):
            pids = list(gen_opt_out_pids_from_database())

            self.assertIn(opt_out_1.pid, pids)
            self.assertIn(opt_out_2.pid, pids)
            self.assertNotIn(opt_out_3.pid, pids)
            self.assertNotIn(opt_out_4.pid, pids)


class ValidateOptoutsTests(DatabaseTestCase):
    def test_error_reported_if_no_valid_optout_fields(self) -> None:
        optout_defining_fields = mock.Mock(
            return_value=[
                (
                    "db",
                    "test_opt_out_bool",
                    "opt_out",
                    "pid",
                    "mpid",
                )
            ]
        )
        mock_dd = mock.Mock(
            get_optout_defining_fields=optout_defining_fields,
        )
        mock_sources = {
            "db": mock.Mock(
                session=self.dbsession,
                engine=self.engine,
                metadata=Base.metadata,
            ),
        }

        TestBoolOptOutFactory(opt_out=True)
        TestBoolOptOutFactory(opt_out=False)
        self.dbsession.flush()

        with mock.patch.multiple(
            "crate_anon.anonymise.anonymise.config",
            dd=mock_dd,
            sources=mock_sources,
            optout_col_values=[3.14159, "1"],
        ):
            with self.assertRaises(ValueError) as cm:
                validate_optouts()

            self.assertEqual(
                str(cm.exception),
                "No valid opt-out values for column 'opt_out'",
            )
