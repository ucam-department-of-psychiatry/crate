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
from typing import Any, Dict, Generator, List, Tuple
from unittest import mock

from cardinal_pythonlib.sqlalchemy.schema import mssql_table_has_ft_index
import factory
import pytest
from sqlalchemy import (
    Boolean,
    Column,
    create_engine,
    inspect,
    Integer,
    String,
)

from crate_anon.anonymise.anonymise import (
    create_indexes,
    gen_opt_out_pids_from_database,
    validate_optouts,
)
from crate_anon.anonymise.constants import IndexType
from crate_anon.anonymise.ddr import DataDictionaryRow
from crate_anon.testing import Base
from crate_anon.testing.classes import DatabaseTestCase
from crate_anon.testing.factories import BaseFactory


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


class TestAnonPatient(Base):
    __tablename__ = "anon_patient"

    pid = Column(Integer, primary_key=True, comment="Patient ID")
    forename = Column(String(50), comment="Forename")
    surname = Column(String(50), comment="Surname")


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


class CreateIndexesTests(DatabaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self._engine_outside_transaction = None

    def test_full_text_index_created_with_mysql(self) -> None:
        if self.engine.dialect.name != "mysql":
            pytest.skip("Skipping mysql-only test")

        if self._get_mysql_anon_patient_table_full_text_indexes():
            self._drop_mysql_full_text_indexes()

        indexes = self._get_mysql_anon_patient_table_full_text_indexes()
        self.assertEqual(len(indexes), 0)

        self._make_full_text_index()
        indexes = self._get_mysql_anon_patient_table_full_text_indexes()

        self.assertEqual(len(indexes), 2)
        self.assertEqual(indexes["forename"]["type"], "FULLTEXT")
        self.assertEqual(indexes["surname"]["type"], "FULLTEXT")

    def _drop_mysql_full_text_indexes(self) -> None:
        sql = "DROP INDEX _idxft_forename ON anon_patient"
        self.engine.execute(sql)

        sql = "DROP INDEX _idxft_surname ON anon_patient"
        self.engine.execute(sql)

    def _get_mysql_anon_patient_table_full_text_indexes(
        self,
    ) -> Dict[str, List[Dict[str, Any]]]:
        return {
            i["column_names"][0]: i
            for i in inspect(self.engine).get_indexes("anon_patient")
        }

    def test_full_text_index_created_with_mssql(self) -> None:
        if self.engine.dialect.name != "mssql":
            pytest.skip("Skipping mssql-only test")

        self._drop_mssql_full_text_indexes()

        self.assertFalse(self._mssql_anon_patient_table_has_full_text_index())
        self._make_full_text_index()

        self.assertTrue(self._mssql_anon_patient_table_has_full_text_index())

    def _mssql_anon_patient_table_has_full_text_index(self) -> None:
        return mssql_table_has_ft_index(
            self.engine_outside_transaction, "anon_patient", "dbo"
        )

    def _drop_mssql_full_text_indexes(self) -> None:
        # SQL Server only. Need to be outside a transaction to drop indexes
        sql = """
IF EXISTS (
    SELECT fti.object_id FROM sys.fulltext_indexes fti
    WHERE fti.object_id = OBJECT_ID(N'[dbo].[anon_patient]')
)

DROP FULLTEXT INDEX ON [dbo].[anon_patient]
"""
        self.engine_outside_transaction.execute(sql)

    @property
    def engine_outside_transaction(self) -> None:
        if self._engine_outside_transaction is None:
            self._engine_outside_transaction = create_engine(
                self.engine.url,
                encoding="utf-8",
                connect_args={"autocommit": True},  # for pyodbc
            )

        return self._engine_outside_transaction

    def _make_full_text_index(self) -> None:
        mock_config = None

        def index_row_sets(
            tasknum: int = 0, ntasks: int = 1
        ) -> Generator[Tuple[str, List[DataDictionaryRow]], None, None]:
            forename_row = DataDictionaryRow(mock_config)
            forename_row.dest_field = "forename"
            forename_row.index = IndexType.FULLTEXT
            surname_row = DataDictionaryRow(mock_config)
            surname_row.dest_field = "surname"
            surname_row.index = IndexType.FULLTEXT

            for set in [
                ("TestAnonPatient", [forename_row, surname_row]),
            ]:
                yield set

        mock_dd = mock.Mock(
            get_dest_sqla_table=mock.Mock(
                return_value=TestAnonPatient.__table__
            )
        )
        with mock.patch.multiple(
            "crate_anon.anonymise.anonymise",
            gen_index_row_sets_by_table=index_row_sets,
        ):
            with mock.patch.multiple(
                "crate_anon.anonymise.anonymise.config",
                dd=mock_dd,
                _destination_database_url=self.engine.url,
            ) as mock_config:
                create_indexes()
