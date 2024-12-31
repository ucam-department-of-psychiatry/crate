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
from sortedcontainers import SortedSet
from sqlalchemy import (
    Boolean,
    Column,
    create_engine,
    inspect,
    Integer,
    String,
    Text,
)

from crate_anon.anonymise.anonymise import (
    create_indexes,
    gen_opt_out_pids_from_database,
    process_patient_tables,
    validate_optouts,
)
from crate_anon.anonymise.constants import IndexType, ScrubMethod
from crate_anon.anonymise.models import PatientInfo
from crate_anon.anonymise.dd import ScrubSourceFieldInfo
from crate_anon.anonymise.ddr import DataDictionaryRow
from crate_anon.anonymise.tests.factories import PatientInfoFactory
from crate_anon.testing import AnonTestBase, SourceTestBase
from crate_anon.testing.classes import DatabaseTestCase
from crate_anon.testing.factories import (
    SourceTestBaseFactory,
    Fake,
)


class TestBoolOptOut(SourceTestBase):
    __tablename__ = "test_opt_out_bool"

    pid = Column(Integer, primary_key=True, comment="Patient ID")
    mpid = Column(Integer, comment="Master patient ID")
    opt_out = Column(Boolean, comment="Opt out?")


class TestBoolOptOutFactory(SourceTestBaseFactory):
    class Meta:
        model = TestBoolOptOut

    pid = factory.Sequence(lambda n: n + 1)
    mpid = factory.Sequence(lambda n: n + 1)


class TestStringOptOut(SourceTestBase):
    __tablename__ = "test_opt_out_string"

    pid = Column(Integer, primary_key=True, comment="Patient ID")
    mpid = Column(Integer, comment="Master patient ID")
    opt_out = Column(String(4), comment="Opt out?")


class TestStringOptOutFactory(SourceTestBaseFactory):
    class Meta:
        model = TestStringOptOut

    pid = factory.Sequence(lambda n: n + 1)
    mpid = factory.Sequence(lambda n: n + 1)


class TestAnonNote(AnonTestBase):
    __tablename__ = "test_anon_note"

    note_id = Column(Integer, primary_key=True, comment="Note ID")
    note1 = Column(Text, comment="Text of note 1")
    note2 = Column(Text, comment="Text of note 2")


class TestPatientWithStringMPID(SourceTestBase):
    __tablename__ = "test_patient_with_string_mpid"

    pid = Column(Integer, primary_key=True, comment="Patient ID")
    nhsnum = Column(String(10), comment="NHS Number")


class TestPatientWithStringMPIDFactory(SourceTestBaseFactory):
    class Meta:
        model = TestPatientWithStringMPID

    pid = factory.Sequence(lambda n: n + 1)

    nhsnum = factory.LazyFunction(Fake.en_gb.nhs_number)


class TestRecord(SourceTestBase):
    __tablename__ = "test_record"

    pk = Column(Integer, primary_key=True, comment="PK")
    pid = Column(Integer, comment="Patient ID")
    row_identifier = Column(Integer, comment="Row ID")


class TestRecordFactory(SourceTestBaseFactory):
    class Meta:
        model = TestRecord

    pk = factory.Sequence(lambda n: n + 1)


class TestAnonRecord(AnonTestBase):
    __tablename__ = "test_anon_record"

    row_identifier = Column(Integer, primary_key=True, comment="Row ID")


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
                session=self.source_dbsession,
                engine=self.source_engine,
                metadata=SourceTestBase.metadata,
            ),
        }

        opt_out_1 = TestBoolOptOutFactory(opt_out=True)
        opt_out_2 = TestBoolOptOutFactory(opt_out=True)
        opt_out_3 = TestBoolOptOutFactory(opt_out=True)
        opt_out_4 = TestBoolOptOutFactory(opt_out=False)
        self.source_dbsession.flush()

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
                session=self.source_dbsession,
                engine=self.source_engine,
                metadata=SourceTestBase.metadata,
            ),
        }

        TestBoolOptOutFactory(opt_out=True)
        self.source_dbsession.flush()

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
                session=self.source_dbsession,
                engine=self.source_engine,
                metadata=SourceTestBase.metadata,
            ),
        }

        opt_out_1 = TestStringOptOutFactory(opt_out="yes")
        opt_out_2 = TestStringOptOutFactory(opt_out="1")
        opt_out_3 = TestStringOptOutFactory(opt_out="no")
        opt_out_4 = TestStringOptOutFactory(opt_out="0")
        self.source_dbsession.flush()

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
                session=self.source_dbsession,
                engine=self.source_engine,
                metadata=SourceTestBase.metadata,
            ),
        }

        TestBoolOptOutFactory(opt_out=True)
        TestBoolOptOutFactory(opt_out=False)
        self.source_dbsession.flush()

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
        if self.anon_engine.dialect.name != "mysql":
            pytest.skip("Skipping MySQL-only test")

        if self._get_mysql_anon_note_table_full_text_indexes():
            self._drop_mysql_full_text_indexes()

        indexes = self._get_mysql_anon_note_table_full_text_indexes()
        self.assertEqual(len(indexes), 0)

        self._make_full_text_index()
        indexes = self._get_mysql_anon_note_table_full_text_indexes()

        self.assertEqual(len(indexes), 2)
        self.assertEqual(indexes["note1"]["type"], "FULLTEXT")
        self.assertEqual(indexes["note2"]["type"], "FULLTEXT")

    def _drop_mysql_full_text_indexes(self) -> None:
        sql = "DROP INDEX _idxft_note1 ON test_anon_note"
        self.anon_engine.execute(sql)

        sql = "DROP INDEX _idxft_note2 ON test_anon_note"
        self.anon_engine.execute(sql)

    def _get_mysql_anon_note_table_full_text_indexes(
        self,
    ) -> Dict[str, List[Dict[str, Any]]]:
        return {
            i["column_names"][0]: i
            for i in inspect(self.anon_engine).get_indexes("test_anon_note")
        }

    def test_full_text_index_created_with_mssql(self) -> None:
        if self.anon_engine.dialect.name != "mssql":
            pytest.skip("Skipping mssql-only test")

        self._drop_mssql_full_text_indexes()

        self.assertFalse(self._mssql_anon_note_table_has_full_text_index())
        self._make_full_text_index()

        self.assertTrue(self._mssql_anon_note_table_has_full_text_index())

    def _mssql_anon_note_table_has_full_text_index(self) -> None:
        return mssql_table_has_ft_index(
            self.anon_engine_outside_transaction, "test_anon_note", "dbo"
        )

    def _drop_mssql_full_text_indexes(self) -> None:
        # SQL Server only. Need to be outside a transaction to drop indexes
        sql = """
IF EXISTS (
    SELECT fti.object_id FROM sys.fulltext_indexes fti
    WHERE fti.object_id = OBJECT_ID(N'[dbo].[test_anon_note]')
)

DROP FULLTEXT INDEX ON [dbo].[test_anon_note]
"""
        self.anon_engine_outside_transaction.execute(sql)

    @property
    def engine_outside_transaction(self) -> None:
        if self._engine_outside_transaction is None:
            self._engine_outside_transaction = create_engine(
                self.anon_engine.url,
                encoding="utf-8",
                connect_args={"autocommit": True},  # for pyodbc
            )

        return self._engine_outside_transaction

    def _make_full_text_index(self) -> None:
        mock_config = None

        def index_row_sets(
            tasknum: int = 0, ntasks: int = 1
        ) -> Generator[Tuple[str, List[DataDictionaryRow]], None, None]:
            note1_row = DataDictionaryRow(mock_config)
            note1_row.dest_field = "note1"
            note1_row.index = IndexType.FULLTEXT
            note2_row = DataDictionaryRow(mock_config)
            note2_row.dest_field = "note2"
            note2_row.index = IndexType.FULLTEXT

            for set in [
                ("TestAnonNote", [note1_row, note2_row]),
            ]:
                yield set

        mock_dd = mock.Mock(
            get_dest_sqla_table=mock.Mock(return_value=TestAnonNote.__table__)
        )
        with mock.patch.multiple(
            "crate_anon.anonymise.anonymise",
            gen_index_row_sets_by_table=index_row_sets,
        ):
            with mock.patch.multiple(
                "crate_anon.anonymise.anonymise.config",
                dd=mock_dd,
                _destination_database_url=self.anon_engine.url,
            ) as mock_config:
                create_indexes()


class ProcessPatientTablesMPidTests(DatabaseTestCase):
    def setUp(self) -> None:
        super().setUp()

        self.mock_admindb = mock.Mock(session=self.secret_dbsession)
        mock_srccfg = mock.Mock(debug_limited_tables=[])
        self.mock_sourcedb = mock.Mock(
            session=self.source_dbsession,
            srccfg=mock_srccfg,
            engine=self.source_engine,
            metadata=SourceTestBase.metadata,
        )
        self.mock_get_scrub_from_rows_as_fieldinfo = mock.Mock(
            return_value=[
                ScrubSourceFieldInfo(
                    is_mpid=True,
                    is_patient=False,
                    recurse=False,
                    required_scrubber=False,
                    scrub_method=ScrubMethod.NUMERIC,
                    signature=None,
                    value_fieldname="nhsnum",
                ),
            ]
        )

        self.mock_get_scrub_from_db_table_pairs = mock.Mock(
            return_value=[
                ("source1", "test_patient_with_string_mpid"),
            ]
        )

        self.mock_get_pid_name = mock.Mock(return_value="pid")
        self.mock_estimate_count_patients = mock.Mock(return_value=1)
        self.mock_opting_out_pid = mock.Mock(return_value=False)

        mock_row = mock.Mock(
            omit=False,
            src_field="row_identifier",
            skip_row_by_value=mock.Mock(return_value=False),
            primary_pid=False,
            master_pid=False,
            third_party_pid=False,
            alter_methods=[],
            dest_field="row_identifier",
            add_src_hash=False,
        )
        mock_rows_for_src_table = mock.Mock(return_value=[mock_row])

        self.mock_dd = mock.Mock(
            get_scrub_from_db_table_pairs=(
                self.mock_get_scrub_from_db_table_pairs
            ),
            get_scrub_from_rows_as_fieldinfo=(
                self.mock_get_scrub_from_rows_as_fieldinfo
            ),
            get_pid_name=self.mock_get_pid_name,
            get_mandatory_scrubber_sigs=mock.Mock(return_value=set()),
            get_source_databases=mock.Mock(
                return_value=SortedSet(["source1"])
            ),
            get_patient_src_tables_with_active_dest=mock.Mock(
                return_value=SortedSet(["test_record"])
            ),
            get_rows_for_src_table=mock_rows_for_src_table,
        )

    def test_patient_saved_in_secret_database(self) -> None:
        patient = TestPatientWithStringMPIDFactory()
        self.source_dbsession.commit()

        pids = [patient.pid]

        with mock.patch.multiple(
            "crate_anon.anonymise.anonymise",
            estimate_count_patients=self.mock_estimate_count_patients,
            opting_out_pid=self.mock_opting_out_pid,
        ):
            with mock.patch.multiple(
                "crate_anon.anonymise.anonymise.config",
                dd=self.mock_dd,
                _destination_database_url=self.anon_engine.url,
                admindb=self.mock_admindb,
                sources={"source1": self.mock_sourcedb},
            ):
                process_patient_tables(specified_pids=pids)

        patient_info = self.secret_dbsession.query(PatientInfo).one()
        self.assertEqual(patient_info.pid, patient.pid)
        self.assertEqual(str(patient_info.mpid), patient.nhsnum)

    def test_patient_mpid_updated_in_secret_database(self) -> None:
        patient = TestPatientWithStringMPIDFactory()
        self.source_dbsession.commit()

        patient_info = PatientInfoFactory(pid=patient.pid, mpid=None)
        self.secret_dbsession.commit()

        pids = [patient.pid]

        with mock.patch.multiple(
            "crate_anon.anonymise.anonymise",
            estimate_count_patients=self.mock_estimate_count_patients,
            opting_out_pid=self.mock_opting_out_pid,
        ):
            with mock.patch.multiple(
                "crate_anon.anonymise.anonymise.config",
                dd=self.mock_dd,
                _destination_database_url=self.anon_engine.url,
                admindb=self.mock_admindb,
                sources={"source1": self.mock_sourcedb},
            ):
                process_patient_tables(specified_pids=pids)

        patient_info = self.secret_dbsession.query(PatientInfo).one()
        self.assertEqual(patient_info.pid, patient.pid)
        self.assertEqual(str(patient_info.mpid), patient.nhsnum)

    def test_patient_with_invalid_mpid_skipped(self) -> None:
        if self.source_engine.dialect.name == "sqlite":
            pytest.skip(
                "Skipping test because SQLite would allow non-integer values "
                "in an integer field"
            )

        patient = TestPatientWithStringMPIDFactory(nhsnum="ABC123")
        self.source_dbsession.commit()

        pid = patient.pid
        pids = [pid]

        with mock.patch.multiple(
            "crate_anon.anonymise.anonymise",
            estimate_count_patients=self.mock_estimate_count_patients,
            opting_out_pid=self.mock_opting_out_pid,
        ):
            with mock.patch.multiple(
                "crate_anon.anonymise.anonymise.config",
                dd=self.mock_dd,
                _destination_database_url=self.anon_engine.url,
                admindb=self.mock_admindb,
                sources={"source1": self.mock_sourcedb},
            ):
                with self.assertLogs(level=logging.WARNING) as logging_cm:
                    process_patient_tables(specified_pids=pids)

        self.assertIsNone(
            self.secret_dbsession.query(PatientInfo).one_or_none()
        )
        logger_name = "crate_anon.anonymise.anonymise"
        expected_message = (
            f"Skipping patient with PID={pid} because the record could "
            "not be saved to the secret_map table"
        )
        self.assertIn(
            f"WARNING:{logger_name}:{expected_message}", logging_cm.output
        )


class ProcessPatientTablesPKTests(DatabaseTestCase):
    def setUp(self) -> None:
        super().setUp()

        self.mock_admindb = mock.Mock(session=self.secret_dbsession)
        self.mock_destdb = mock.Mock(
            session=self.anon_dbsession,
            engine=self.anon_engine,
            metadata=AnonTestBase.metadata,
        )
        mock_srccfg = mock.Mock(debug_limited_tables=[])
        self.mock_sourcedb = mock.Mock(
            session=self.source_dbsession,
            srccfg=mock_srccfg,
            engine=self.source_engine,
            metadata=SourceTestBase.metadata,
        )
        self.mock_get_scrub_from_rows_as_fieldinfo = mock.Mock(
            return_value=[
                ScrubSourceFieldInfo(
                    is_mpid=True,
                    is_patient=False,
                    recurse=False,
                    required_scrubber=False,
                    scrub_method=ScrubMethod.NUMERIC,
                    signature=None,
                    value_fieldname="nhsnum",
                ),
            ]
        )

        self.mock_get_scrub_from_db_table_pairs = mock.Mock(
            return_value=[
                ("source1", "test_patient_with_string_mpid"),
            ]
        )

        self.mock_get_pid_name = mock.Mock(return_value="pid")
        self.mock_estimate_count_patients = mock.Mock(return_value=1)
        self.mock_opting_out_pid = mock.Mock(return_value=False)

        mock_row = mock.Mock(
            omit=False,
            src_field="row_identifier",
            skip_row_by_value=mock.Mock(return_value=False),
            primary_pid=False,
            master_pid=False,
            third_party_pid=False,
            alter_methods=[],
            dest_field="row_identifier",
            add_src_hash=False,
        )
        mock_rows_for_src_table = mock.Mock(return_value=[mock_row])

        self.mock_dd = mock.Mock(
            get_scrub_from_db_table_pairs=(
                self.mock_get_scrub_from_db_table_pairs
            ),
            get_scrub_from_rows_as_fieldinfo=(
                self.mock_get_scrub_from_rows_as_fieldinfo
            ),
            get_pid_name=self.mock_get_pid_name,
            get_mandatory_scrubber_sigs=mock.Mock(return_value=set()),
            get_source_databases=mock.Mock(
                return_value=SortedSet(["source1"])
            ),
            get_patient_src_tables_with_active_dest=mock.Mock(
                return_value=SortedSet(["test_record"])
            ),
            get_rows_for_src_table=mock_rows_for_src_table,
            get_dest_sqla_table=mock.Mock(
                return_value=TestAnonRecord.__table__
            ),
        )

    def test_duplicate_primary_key_skipped(self) -> None:
        # MySQL supports ON DUPLICATE KEY UPDATE
        if self.anon_engine.dialect.name == "mysql":
            pytest.skip("Skipping different behaviour for MySQL")

        patient = TestPatientWithStringMPIDFactory()
        TestRecordFactory(pid=patient.pid, row_identifier=123456)
        TestRecordFactory(pid=patient.pid, row_identifier=123456)
        self.source_dbsession.commit()

        pids = [patient.pid]

        with mock.patch.multiple(
            "crate_anon.anonymise.anonymise",
            estimate_count_patients=self.mock_estimate_count_patients,
            opting_out_pid=self.mock_opting_out_pid,
        ):
            with mock.patch.multiple(
                "crate_anon.anonymise.anonymise.config",
                dd=self.mock_dd,
                _destination_database_url=self.anon_engine.url,
                admindb=self.mock_admindb,
                destdb=self.mock_destdb,
                sources={"source1": self.mock_sourcedb},
                rows_inserted_per_table={("source1", "test_record"): 0},
                timefield=None,
            ):
                with self.assertLogs(level=logging.WARNING) as logging_cm:
                    process_patient_tables(specified_pids=pids)

        logger_name = "crate_anon.anonymise.anonymise"
        expected_message = "Skipping record due to IntegrityError"
        self.assertIn(
            f"WARNING:{logger_name}:{expected_message}", logging_cm.output[0]
        )

        self.assertEqual(self.anon_dbsession.query(TestAnonRecord).count(), 1)
