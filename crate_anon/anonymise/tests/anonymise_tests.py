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

# =============================================================================
# Imports
# =============================================================================

import logging
from typing import Any, Dict, Generator, List, Tuple, TYPE_CHECKING
from unittest import mock

from cardinal_pythonlib.hash import HmacMD5Hasher
from cardinal_pythonlib.sqlalchemy.schema import (
    execute_ddl,
    mssql_table_has_ft_index,
)
import factory
import pytest
from sortedcontainers import SortedSet
from sqlalchemy import (
    Boolean,
    Column,
    create_engine,
    DateTime,
    inspect,
    Integer,
    String,
    Text,
)

from crate_anon.anonymise.anonymise import (
    create_indexes,
    gen_opt_out_pids_from_database,
    process_patient_tables,
    process_table,
    validate_optouts,
)
from crate_anon.anonymise.altermethod import AlterMethod
from crate_anon.anonymise.constants import IndexType, ScrubMethod
from crate_anon.anonymise.models import PatientInfo
from crate_anon.anonymise.dd import ScrubSourceFieldInfo
from crate_anon.anonymise.ddr import DataDictionaryRow
from crate_anon.anonymise.tests.factories import PatientInfoFactory
from crate_anon.testing import AnonTestBase, SourceTestBase
from crate_anon.testing.classes import (
    DatabaseTestCase,
    SlowSecretDatabaseTestCase,
)
from crate_anon.testing.factories import (
    AnonTestBaseFactory,
    Fake,
    SourceTestBaseFactory,
)

if TYPE_CHECKING:
    from factory.builder import Resolver


# =============================================================================
# SQLAlchemy test tables
# =============================================================================


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


class TestPatient(SourceTestBase):
    __tablename__ = "test_patient"

    pid = Column(Integer, primary_key=True, comment="Patient ID")
    forename = Column(String(50), comment="Forename")
    surname = Column(String(50), comment="Surname")

    @property
    def name(self) -> str:
        return f"{self.forename} {self.surname}"


class TestPatientFactory(SourceTestBaseFactory):
    class Meta:
        model = TestPatient

    forename = factory.LazyFunction(Fake.en_gb.first_name)
    surname = factory.LazyFunction(Fake.en_gb.last_name)


class TestPatientWithStringMPID(SourceTestBase):
    __tablename__ = "test_patient_with_string_mpid"

    pid = Column(Integer, primary_key=True, comment="Patient ID")
    nhsnum = Column(String(10), comment="NHS Number")


class TestPatientWithStringMPIDFactory(SourceTestBaseFactory):
    class Meta:
        model = TestPatientWithStringMPID

    pid = factory.Sequence(lambda n: n + 1)

    @factory.lazy_attribute
    def nhsnum(obj: "Resolver") -> str:
        return str(Fake.en_gb.nhs_number())


class TestRecord(SourceTestBase):
    __tablename__ = "test_record"

    pk = Column(Integer, primary_key=True, comment="PK")
    pid = Column(Integer, comment="Patient ID")
    row_identifier = Column(Integer, comment="Row ID")
    other = Column(String(50), comment="Other column")


class TestRecordFactory(SourceTestBaseFactory):
    class Meta:
        model = TestRecord

    pk = factory.Sequence(lambda n: n + 1)
    row_identifier = factory.Sequence(lambda n: n + 10000)


class TestAnonRecord(AnonTestBase):
    __tablename__ = "test_anon_record"

    row_identifier = Column(Integer, primary_key=True, comment="Row ID")
    other = Column(String(50), comment="Other column")
    _src_hash = Column(String(32))
    _when_processed_utc = Column(DateTime())


class TestAnonRecordFactory(AnonTestBaseFactory):
    class Meta:
        model = TestAnonRecord


class TestPidAsPkRecord(SourceTestBase):
    __tablename__ = "test_pid_as_pk_record"

    pid = Column(Integer, primary_key=True, comment="Patient ID")
    other = Column(String(50), comment="Other column")


class TestPidAsPkRecordFactory(SourceTestBaseFactory):
    class Meta:
        model = TestPidAsPkRecord


class TestAnonPidAsPkRecord(AnonTestBase):
    __tablename__ = "test_anon_pid_as_pk_record"

    rid = Column(String(32), primary_key=True, comment="Research ID")
    _src_hash = Column(String(32))
    _when_processed_utc = Column(DateTime())


class TestAnonPidAsPkRecordFactory(AnonTestBaseFactory):
    class Meta:
        model = TestAnonPidAsPkRecord


# =============================================================================
# Unit tests
# =============================================================================
class AnonymiseTestMixin:
    def mock_dd_row(
        self,
        omit: bool = False,
        skip_row_by_value: mock.Mock = None,
        primary_pid: bool = False,
        master_pid: bool = False,
        third_party_pid: bool = False,
        alter_methods: list[AlterMethod] = None,
        add_src_hash: bool = False,
        **kwargs,
    ) -> mock.Mock:
        if skip_row_by_value is None:
            skip_row_by_value = mock.Mock(return_value=False)

        if alter_methods is None:
            alter_methods = []

        return mock.Mock(
            omit=omit,
            skip_row_by_value=skip_row_by_value,
            primary_pid=primary_pid,
            master_pid=master_pid,
            third_party_pid=third_party_pid,
            alter_methods=alter_methods,
            add_src_hash=add_src_hash,
            **kwargs,
        )


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
        execute_ddl(
            self.anon_engine, sql="DROP INDEX _idxft_note1 ON test_anon_note"
        )
        execute_ddl(
            self.anon_engine, sql="DROP INDEX _idxft_note2 ON test_anon_note"
        )

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

    def _mssql_anon_note_table_has_full_text_index(self) -> bool:
        return mssql_table_has_ft_index(
            self.engine_outside_transaction, "test_anon_note", "dbo"
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
        execute_ddl(self.engine_outside_transaction, sql)

    @property
    def engine_outside_transaction(self) -> None:
        if self._engine_outside_transaction is None:
            self._engine_outside_transaction = create_engine(
                self.anon_engine.url,
                connect_args={"autocommit": True},  # for pyodbc
                future=True,
            )

        return self._engine_outside_transaction

    def _make_full_text_index(self) -> None:
        mock_config = None

        # noinspection PyUnusedLocal
        def index_row_sets(
            tasknum: int = 0, ntasks: int = 1
        ) -> Generator[Tuple[str, List[DataDictionaryRow]], None, None]:
            note1_row = DataDictionaryRow(mock_config)
            note1_row.dest_field = "note1"
            note1_row.index = IndexType.FULLTEXT
            note2_row = DataDictionaryRow(mock_config)
            note2_row.dest_field = "note2"
            note2_row.index = IndexType.FULLTEXT

            for set_ in [
                ("TestAnonNote", [note1_row, note2_row]),
            ]:
                yield set_

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


class ProcessPatientTablesMPidTests(
    SlowSecretDatabaseTestCase, AnonymiseTestMixin
):
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

        mock_row = self.mock_dd_row(
            src_field="row_identifier",
            dest_field="row_identifier",
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

        patient_info = self.secret_dbsession.query(PatientInfo).one_or_none()
        self.assertIsNone(patient_info)

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

        patient_info = self.secret_dbsession.query(PatientInfo).one_or_none()
        self.assertIsNone(patient_info)

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

    def test_valid_patients_added_when_invalid_mpid_skipped(self) -> None:
        if self.source_engine.dialect.name == "sqlite":
            pytest.skip(
                "Skipping test because SQLite would allow non-integer values "
                "in an integer field"
            )

        patient_info = self.secret_dbsession.query(PatientInfo).one_or_none()
        self.assertIsNone(patient_info)
        invalid_patient = TestPatientWithStringMPIDFactory(nhsnum="ABC123")
        self.source_dbsession.commit()
        valid_patient1 = TestPatientWithStringMPIDFactory()
        self.source_dbsession.commit()
        valid_patient2 = TestPatientWithStringMPIDFactory()
        self.source_dbsession.commit()

        invalid_pid = invalid_patient.pid
        valid_pid1 = valid_patient1.pid
        valid_pid2 = valid_patient2.pid
        pids = [valid_pid1, invalid_pid, valid_pid2]

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

        pids = [p.pid for p in self.secret_dbsession.query(PatientInfo)]
        self.assertIn(valid_patient1.pid, pids)
        self.assertIn(valid_patient2.pid, pids)

        # For some reason these end up being a mixture of strings and ints
        nhsnums = [
            int(p.mpid) for p in self.secret_dbsession.query(PatientInfo)
        ]
        self.assertIn(int(valid_patient1.nhsnum), nhsnums)
        self.assertIn(int(valid_patient2.nhsnum), nhsnums)


class ProcessPatientTablesPKTests(DatabaseTestCase, AnonymiseTestMixin):
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

        mock_row = self.mock_dd_row(
            src_field="row_identifier",
            dest_field="row_identifier",
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
        # row_identifier is the primary key in the destination
        # database but not in the source

        # MySQL supports ON DUPLICATE KEY UPDATE
        if self.anon_engine.dialect.name == "mysql":
            pytest.skip("Skipping different behaviour for MySQL")

        patient = TestPatientWithStringMPIDFactory()
        record = TestRecordFactory(pid=patient.pid)
        TestRecordFactory(
            pid=patient.pid, row_identifier=record.row_identifier
        )
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
        self.assertTrue(
            any(
                f"WARNING:{logger_name}:{expected_message}" in line
                for line in logging_cm.output
            )
        )

        self.assertEqual(self.anon_dbsession.query(TestAnonRecord).count(), 1)


class ProcessTableTests(DatabaseTestCase, AnonymiseTestMixin):
    def setUp(self) -> None:
        super().setUp()

        # Passphrases match those in get_demo_config()
        self.pid_hasher = HmacMD5Hasher("SOME_PASSPHRASE_REPLACE_ME")
        self.mpid_hasher = HmacMD5Hasher("SOME_OTHER_PASSPHRASE_REPLACE_ME")
        self.change_hasher = HmacMD5Hasher("YETANOTHER")

        mock_srccfg = mock.Mock(debug_limited_tables=[])
        self.mock_sourcedb = mock.Mock(
            session=self.source_dbsession,
            srccfg=mock_srccfg,
            engine=self.source_engine,
            metadata=SourceTestBase.metadata,
        )

        self.mock_destdb = mock.Mock(
            session=self.anon_dbsession,
            engine=self.anon_engine,
            metadata=AnonTestBase.metadata,
        )

    def test_record_anonymised(self) -> None:
        patient = TestPatientFactory()
        self.source_dbsession.commit()
        TestRecordFactory(pid=patient.pid, other="Personal information")
        self.source_dbsession.commit()

        mock_alter_method = mock.Mock(
            alter=mock.Mock(return_value=("ANONYMISED", False))
        )

        mock_rows = [
            self.mock_dd_row(
                omit=True,
                src_field="pk",
                dest_table="test_anon_record",
                dest_field="pk",
            ),
            self.mock_dd_row(
                omit=True,
                src_field="pid",
                dest_table="test_anon_record",
                dest_field="pid",
            ),
            self.mock_dd_row(
                src_field="row_identifier",
                dest_table="test_anon_record",
                dest_field="row_identifier",
            ),
            self.mock_dd_row(
                src_field="other",
                dest_table="test_anon_record",
                dest_field="other",
                alter_methods=[mock_alter_method],
            ),
        ]
        mock_rows_for_src_table = mock.Mock(return_value=mock_rows)

        mock_dd = mock.Mock(
            get_rows_for_src_table=mock_rows_for_src_table,
            get_dest_sqla_table=mock.Mock(
                return_value=TestAnonRecord.__table__
            ),
        )

        with mock.patch.multiple(
            "crate_anon.anonymise.anonymise.config",
            dd=mock_dd,
            sources={"source": self.mock_sourcedb},
            _destination_database_url=self.anon_engine.url,
            destdb=self.mock_destdb,
            rows_inserted_per_table={("source", "test_record"): 0},
        ):
            process_table("source", "test_record", incremental=True)

        anon_record = self.anon_dbsession.query(TestAnonRecord).one()

        self.assertEqual(anon_record.other, "ANONYMISED")

    def test_unchanged_record_matching_hash_with_plain_rid_skipped(
        self,
    ) -> None:
        patient = TestPatientFactory()
        self.source_dbsession.commit()
        test_record = TestRecordFactory(pid=patient.pid)
        self.source_dbsession.commit()
        TestAnonRecordFactory(
            row_identifier=test_record.row_identifier,
            _src_hash=self.change_hasher.hash(
                repr([test_record.row_identifier])
            ),
        )
        self.anon_dbsession.commit()

        mock_row = self.mock_dd_row(
            src_field="row_identifier",
            dest_table="test_anon_record",
            dest_field="row_identifier",
            add_src_hash=True,
        )
        mock_rows_for_src_table = mock.Mock(return_value=[mock_row])

        mock_dd = mock.Mock(
            get_rows_for_src_table=mock_rows_for_src_table,
            get_dest_sqla_table=mock.Mock(
                return_value=TestAnonRecord.__table__
            ),
        )
        with mock.patch.multiple(
            "crate_anon.anonymise.anonymise.config",
            dd=mock_dd,
            sources={"source": self.mock_sourcedb},
            _destination_database_url=self.anon_engine.url,
            destdb=self.mock_destdb,
            rows_inserted_per_table={("source", "test_record"): 0},
        ):
            with self.assertLogs(level=logging.DEBUG) as logging_cm:
                process_table("source", "test_record", incremental=True)

        logger_name = "crate_anon.anonymise.anonymise"
        expected_message = (
            "... ... skipping unchanged record (identical by hash): "
        )

        self.assertTrue(
            any(
                f"DEBUG:{logger_name}:{expected_message}" in line
                for line in logging_cm.output
            )
        )

    def test_unchanged_record_matching_hash_with_hashed_rid_skipped(
        self,
    ) -> None:
        patient = TestPatientFactory()
        self.source_dbsession.commit()
        test_record = TestPidAsPkRecordFactory(pid=patient.pid, other="Other")
        self.source_dbsession.commit()
        TestAnonPidAsPkRecordFactory(
            rid=self.pid_hasher.hash(patient.pid),
            _src_hash=self.change_hasher.hash(repr([test_record.pid])),
        )
        self.anon_dbsession.commit()

        mock_row = self.mock_dd_row(
            src_field="pid",
            primary_pid=True,
            dest_table="test_anon_pid_as_pk_record",
            dest_field="rid",
            add_src_hash=True,
        )
        mock_rows_for_src_table = mock.Mock(return_value=[mock_row])

        mock_dd = mock.Mock(
            get_rows_for_src_table=mock_rows_for_src_table,
            get_dest_sqla_table=mock.Mock(
                return_value=TestAnonPidAsPkRecord.__table__
            ),
            get_pid_name=mock.Mock(return_value="pid"),
        )
        mock_patient = mock.Mock(pid=patient.pid)
        with mock.patch.multiple(
            "crate_anon.anonymise.anonymise.config",
            dd=mock_dd,
            sources={"source": self.mock_sourcedb},
            _destination_database_url=self.anon_engine.url,
            destdb=self.mock_destdb,
            rows_inserted_per_table={("source", "test_pid_as_pk_record"): 0},
        ):
            with self.assertLogs(level=logging.DEBUG) as logging_cm:
                process_table(
                    "source",
                    "test_pid_as_pk_record",
                    patient=mock_patient,
                    incremental=True,
                )

        logger_name = "crate_anon.anonymise.anonymise"
        expected_message = (
            "... ... skipping unchanged record (identical by hash): "
        )

        self.assertTrue(
            any(
                f"DEBUG:{logger_name}:{expected_message}" in line
                for line in logging_cm.output
            )
        )

    def test_constant_record_matching_pk_skipped(
        self,
    ) -> None:
        patient = TestPatientFactory()
        self.source_dbsession.commit()
        test_record = TestRecordFactory(pid=patient.pid)
        self.source_dbsession.commit()
        TestAnonRecordFactory(
            row_identifier=test_record.row_identifier,
        )
        self.anon_dbsession.commit()

        mock_row = self.mock_dd_row(
            src_field="row_identifier",
            dest_table="test_anon_record",
            dest_field="row_identifier",
            constant=True,
        )
        mock_rows_for_src_table = mock.Mock(return_value=[mock_row])

        mock_dd = mock.Mock(
            get_rows_for_src_table=mock_rows_for_src_table,
            get_dest_sqla_table=mock.Mock(
                return_value=TestAnonRecord.__table__
            ),
        )
        with mock.patch.multiple(
            "crate_anon.anonymise.anonymise.config",
            dd=mock_dd,
            sources={"source": self.mock_sourcedb},
            _destination_database_url=self.anon_engine.url,
            destdb=self.mock_destdb,
            rows_inserted_per_table={("source", "test_record"): 0},
        ):
            with self.assertLogs(level=logging.DEBUG) as logging_cm:
                process_table("source", "test_record", incremental=True)

        logger_name = "crate_anon.anonymise.anonymise"
        expected_message = (
            "... ... skipping unchanged record (identical by PK and "
            "marked as constant): "
        )

        self.assertTrue(
            any(
                f"DEBUG:{logger_name}:{expected_message}" in line
                for line in logging_cm.output
            )
        )

    def test_does_nothing_if_all_ddrows_omitted(self) -> None:
        patient = TestPatientFactory()
        self.source_dbsession.commit()
        TestRecordFactory(pid=patient.pid)
        self.source_dbsession.commit()

        mock_rows = [
            self.mock_dd_row(
                omit=True,
                src_field="pk",
                dest_table="test_anon_record",
                dest_field="pk",
                add_src_hash=True,
            ),
            self.mock_dd_row(
                omit=True,
                src_field="pid",
                dest_table="test_anon_record",
                dest_field="pid",
                add_src_hash=True,
            ),
            self.mock_dd_row(
                omit=True,
                src_field="row_identifier",
                dest_table="test_anon_record",
                dest_field="row_identifier",
                add_src_hash=True,
            ),
        ]
        mock_rows_for_src_table = mock.Mock(return_value=mock_rows)

        mock_dd = mock.Mock(
            get_rows_for_src_table=mock_rows_for_src_table,
            get_dest_sqla_table=mock.Mock(
                return_value=TestAnonRecord.__table__
            ),
        )
        with mock.patch.multiple(
            "crate_anon.anonymise.anonymise.config",
            dd=mock_dd,
            sources={"source": self.mock_sourcedb},
            _destination_database_url=self.anon_engine.url,
            destdb=self.mock_destdb,
            rows_inserted_per_table={("source", "test_record"): 0},
        ):
            with self.assertLogs(level=logging.DEBUG) as logging_cm:
                process_table("source", "test_record", incremental=True)

        logger_name = "crate_anon.anonymise.anonymise"
        expected_message = "... ... all columns omitted"

        self.assertTrue(
            any(
                f"DEBUG:{logger_name}:{expected_message}" in line
                for line in logging_cm.output
            )
        )
