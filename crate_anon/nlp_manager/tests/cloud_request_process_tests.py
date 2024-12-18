"""
crate_anon/nlp_manager/tests/cloud_request_process_tests.py

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

Unit tests.

Reminder: to enable logging, use e.g. pytest -k [testname] --log-cli-level=INFO

"""

import json
import logging
import os
from pathlib import Path
import sys
from unittest import mock, TestCase
from tempfile import TemporaryDirectory
from typing import Any, Dict

from cardinal_pythonlib.httpconst import HttpStatus
from sqlalchemy.engine import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.schema import Column

from crate_anon.nlp_manager.all_processors import (
    register_all_crate_python_processors_with_serverprocessor,
)
from crate_anon.nlp_manager.cloud_parser import Cloud
from crate_anon.nlp_manager.cloud_request import (
    CloudRequest,
    CloudRequestListProcessors,
    CloudRequestProcess,
)
from crate_anon.nlp_manager.cloud_run_info import CloudRunInfo
from crate_anon.nlp_manager.constants import (
    CloudNlpConfigKeys,
    DatabaseConfigKeys,
    InputFieldConfigKeys,
    NLP_CONFIG_ENV_VAR,
    NlpConfigPrefixes,
    NlpDefConfigKeys,
    NlpDefValues,
    NlpOutputConfigKeys,
    ProcessorConfigKeys,
)
from crate_anon.nlp_manager.nlp_definition import NlpDefinition
from crate_anon.nlp_manager.nlp_manager import drop_remake, process_cloud_now
from crate_anon.nlp_webserver.server_processor import ServerProcessor
from crate_anon.nlp_webserver.views import NlpWebViews
from crate_anon.nlprp.constants import NlprpKeys as NKeys, NlprpValues

log = logging.getLogger(__name__)


# =============================================================================
# CloudRequestProcessTests
# =============================================================================


class CloudRequestProcessTests(TestCase):
    def setUp(self) -> None:
        self.mock_execute_method = mock.Mock()
        self.mock_session = mock.Mock(execute=self.mock_execute_method)
        self.mock_db = mock.Mock(session=self.mock_session)

        # can't set name attribute in constructor here as it has special
        # meaning
        mock_column = mock.Mock()
        mock_column.name = "fruit"  # so set it here

        self.mock_values_method = mock.Mock()
        mock_insert_object = mock.Mock(values=self.mock_values_method)
        mock_insert_method = mock.Mock(return_value=mock_insert_object)
        mock_sqla_table = mock.Mock(
            columns=[mock_column], insert=mock_insert_method
        )
        mock_get_table_method = mock.Mock(return_value=mock_sqla_table)
        self.mock_processor = mock.Mock(
            get_table=mock_get_table_method, dest_session=self.mock_session
        )

        self.mock_notify_transaction_method = mock.Mock()
        self.mock_nlpdef = mock.Mock(
            notify_transaction=self.mock_notify_transaction_method
        )
        self.mock_nlpdef.name = "fruitdef"
        self.process = CloudRequestProcess(nlpdef=self.mock_nlpdef)

    def test_process_all_inserts_values(self) -> None:
        nlp_values = [
            ("output", {"fruit": "apple"}, self.mock_processor),
            ("output", {"fruit": "banana"}, self.mock_processor),
            ("output", {"fruit": "fig"}, self.mock_processor),
        ]

        mock_get_nlp_values_method = mock.Mock(return_value=iter(nlp_values))

        with mock.patch.multiple(
            self.process, get_nlp_values=mock_get_nlp_values_method
        ):
            self.process.process_all()

        self.mock_values_method.assert_any_call({"fruit": "apple"})
        self.mock_values_method.assert_any_call({"fruit": "banana"})
        self.mock_values_method.assert_any_call({"fruit": "fig"})
        self.assertEqual(self.mock_values_method.call_count, 3)
        self.assertEqual(self.mock_execute_method.call_count, 3)

        self.mock_notify_transaction_method.assert_any_call(
            self.mock_session,
            n_rows=1,
            n_bytes=sys.getsizeof({"fruit": "apple"}),
            force_commit=mock.ANY,
        )
        self.mock_notify_transaction_method.assert_any_call(
            self.mock_session,
            n_rows=1,
            n_bytes=sys.getsizeof({"fruit": "banana"}),
            force_commit=mock.ANY,
        )
        self.mock_notify_transaction_method.assert_any_call(
            self.mock_session,
            n_rows=1,
            n_bytes=sys.getsizeof({"fruit": "fig"}),
            force_commit=mock.ANY,
        )
        self.assertEqual(self.mock_notify_transaction_method.call_count, 3)

    def test_process_all_handles_failed_insert(self) -> None:
        nlp_values = [
            ("output", {"fruit": "apple"}, self.mock_processor),
        ]

        self.mock_execute_method.side_effect = OperationalError(
            "Insert failed", None, None, None
        )

        mock_get_nlp_values_method = mock.Mock(return_value=iter(nlp_values))
        with self.assertLogs(level=logging.ERROR) as logging_cm:
            with mock.patch.multiple(
                self.process, get_nlp_values=mock_get_nlp_values_method
            ):
                self.process.process_all()

        self.mock_notify_transaction_method.assert_any_call(
            self.mock_session,
            n_rows=1,
            n_bytes=sys.getsizeof({"fruit": "apple"}),
            force_commit=mock.ANY,
        )
        logger_name = "crate_anon.nlp_manager.cloud_request"

        self.assertIn(f"ERROR:{logger_name}", logging_cm.output[0])
        self.assertIn("Insert failed", logging_cm.output[0])

    def test_not_ready_if_queue_id_is_none(self) -> None:
        self.process.queue_id = None
        with self.assertLogs(level=logging.WARNING) as logging_cm:
            ready = self.process.check_if_ready()
        self.assertFalse(ready)
        self.assertIn(
            "Tried to fetch from queue before sending request.",
            logging_cm.output[0],
        )

    def test_not_ready_if_fetched(self) -> None:
        self.process.queue_id = "queue_0001"
        self.process._fetched = True

        ready = self.process.check_if_ready()
        self.assertFalse(ready)

    def test_not_ready_if_no_response(self) -> None:
        self.process.queue_id = "queue_0001"
        with mock.patch.object(self.process, "_try_fetch", return_value=None):
            ready = self.process.check_if_ready()
        self.assertFalse(ready)

    def test_ready_for_status_ok(self) -> None:
        self.process.queue_id = "queue_0001"

        response = {
            NKeys.STATUS: HttpStatus.OK,
            NKeys.VERSION: "0.3.0",
        }

        with mock.patch.object(
            self.process, "_try_fetch", return_value=response
        ):
            ready = self.process.check_if_ready()
        self.assertTrue(ready)

    def test_not_ready_when_old_server_status_processing(self) -> None:
        self.process.queue_id = "queue_0001"

        response = {
            NKeys.STATUS: HttpStatus.PROCESSING,
            NKeys.VERSION: "0.2.0",
        }

        with mock.patch.object(
            self.process, "_try_fetch", return_value=response
        ):
            ready = self.process.check_if_ready()
        self.assertFalse(ready)

    def test_not_ready_when_new_server_status_accepted(self) -> None:
        self.process.queue_id = "queue_0001"

        response = {
            NKeys.STATUS: HttpStatus.ACCEPTED,
            NKeys.VERSION: "0.3.0",
        }

        with mock.patch.object(
            self.process, "_try_fetch", return_value=response
        ):
            ready = self.process.check_if_ready()
        self.assertFalse(ready)

    def test_not_ready_when_server_status_not_found(self) -> None:
        self.process.queue_id = "queue_0001"

        response = {
            NKeys.STATUS: HttpStatus.NOT_FOUND,
            NKeys.VERSION: "0.3.0",
        }

        with mock.patch.object(
            self.process, "_try_fetch", return_value=response
        ):
            with self.assertLogs(level=logging.WARNING) as logging_cm:
                ready = self.process.check_if_ready()
        self.assertFalse(ready)
        self.assertIn("Got HTTP status code 404", logging_cm.output[0])

    def test_not_ready_when_server_status_anything_else(self) -> None:
        self.process.queue_id = "queue_0001"

        response = {
            NKeys.STATUS: HttpStatus.FORBIDDEN,
            NKeys.VERSION: "0.3.0",
        }

        with mock.patch.object(
            self.process, "_try_fetch", return_value=response
        ):
            with self.assertLogs(level=logging.WARNING) as logging_cm:
                ready = self.process.check_if_ready()
        self.assertFalse(ready)
        self.assertIn("Got HTTP status code 403", logging_cm.output[0])


# =============================================================================
# CloudRequestListProcessorsTests
# =============================================================================

# A real one that wasn't working, 2024-12-16, with keys parameterized and
# boolean values Pythonized.
TEST_REMOTE_TABLE_SMOKING = "Smoking:Smoking"
TEST_PROCINFO_SMOKING = {
    NKeys.DESCRIPTION: "A description",
    NKeys.IS_DEFAULT_VERSION: True,
    NKeys.NAME: "smoking",
    NKeys.SCHEMA_TYPE: NlprpValues.TABULAR,
    NKeys.SQL_DIALECT: "mssql",
    NKeys.TABULAR_SCHEMA: {
        TEST_REMOTE_TABLE_SMOKING: [
            {
                NKeys.COLUMN_NAME: "start_",
                NKeys.COLUMN_TYPE: "BIGINT",
                NKeys.DATA_TYPE: "BIGINT",
                NKeys.IS_NULLABLE: False,
            },
            {
                NKeys.COLUMN_NAME: "end_",
                NKeys.COLUMN_TYPE: "BIGINT",
                NKeys.DATA_TYPE: "BIGINT",
                NKeys.IS_NULLABLE: False,
            },
            {
                NKeys.COLUMN_NAME: "who",
                NKeys.COLUMN_TYPE: "NVARCHAR(255)",
                NKeys.DATA_TYPE: "NVARCHAR",
                NKeys.IS_NULLABLE: True,
            },
            {
                NKeys.COLUMN_NAME: "rule",
                NKeys.COLUMN_TYPE: "VARCHAR(50)",
                NKeys.DATA_TYPE: "VARCHAR",
                NKeys.IS_NULLABLE: True,
            },
            {
                NKeys.COLUMN_NAME: "status",
                NKeys.COLUMN_TYPE: "VARCHAR(10)",
                NKeys.DATA_TYPE: "VARCHAR",
                NKeys.IS_NULLABLE: True,
            },
        ]
    },
    NKeys.TITLE: "Smoking Status Annotator",
    NKeys.VERSION: "0.1",
}


class CloudRequestListProcessorsTests(TestCase):
    def setUp(self) -> None:
        self.mock_nlpdef = mock.Mock(name="mock_nlpdef")
        self.mock_nlpdef.name = "testlistprocdef"
        self.process = CloudRequestListProcessors(nlpdef=self.mock_nlpdef)
        self.test_version = "0.3.0"

    def test_processors_key_missing(self) -> None:
        response = {
            NKeys.STATUS: HttpStatus.ACCEPTED,
            NKeys.VERSION: self.test_version,
            # Missing: NKeys.PROCESSORS
        }
        with mock.patch.object(
            self.process, "_post_get_json", return_value=response
        ):
            with self.assertRaises(KeyError):
                self.process.get_remote_processors()

    def test_processors_not_list(self) -> None:
        response = {
            NKeys.STATUS: HttpStatus.ACCEPTED,
            NKeys.VERSION: self.test_version,
            NKeys.PROCESSORS: "XXX",  # not a list
        }
        with mock.patch.object(
            self.process, "_post_get_json", return_value=response
        ):
            with self.assertRaises(ValueError):
                self.process.get_remote_processors()

    def test_procinfo_not_dict(self) -> None:
        procinfo = "xxx"  # not a dict
        response = {
            NKeys.STATUS: HttpStatus.ACCEPTED,
            NKeys.VERSION: self.test_version,
            NKeys.PROCESSORS: [procinfo],
        }
        with mock.patch.object(
            self.process, "_post_get_json", return_value=response
        ):
            with self.assertRaises(ValueError):
                self.process.get_remote_processors()

    def test_procinfo_missing_keys(self) -> None:
        mandatory_keys = (
            NKeys.NAME,
            NKeys.TITLE,
            NKeys.VERSION,
            NKeys.DESCRIPTION,
        )
        base_procinfo = {k: "x" for k in mandatory_keys}
        for key in mandatory_keys:
            procinfo = base_procinfo.copy()
            del procinfo[key]
            response = {
                NKeys.STATUS: HttpStatus.ACCEPTED,
                NKeys.VERSION: self.test_version,
                NKeys.PROCESSORS: [procinfo],
            }
            with mock.patch.object(
                self.process, "_post_get_json", return_value=response
            ):
                with self.assertRaises(KeyError):
                    self.process.get_remote_processors()

    def test_procinfo_smoking(self) -> None:
        response = {
            NKeys.STATUS: HttpStatus.ACCEPTED,
            NKeys.VERSION: self.test_version,
            NKeys.PROCESSORS: [TEST_PROCINFO_SMOKING],
        }
        with mock.patch.object(
            self.process, "_post_get_json", return_value=response
        ):
            self.process.get_remote_processors()
            # Should be happy.


# =============================================================================
# CloudRequestDataTests
# =============================================================================


class CloudRequestDataTests(TestCase):
    def setUp(self) -> None:
        # On-disk database
        self.tempdir = TemporaryDirectory()  # will be deleted automatically
        self.dbfilepath = Path(self.tempdir.name, "test.sqlite")
        log.info(f"Using temporary database: {self.dbfilepath}")
        self.dburl = f"sqlite:///{self.dbfilepath.absolute()}"
        self.txttable = "notes"
        self.pkcol = "pk"
        self.txtcol = "note"
        self.echo = False
        self._mk_test_data()

        # Dummy database
        self.dummy_engine = create_engine("sqlite://")

        # Config file
        self.nlpdefname = "mynlp"
        self.dbsectionname = "mydb"
        self.cloudconfigname = "mycloud"
        self.inputname = "myinput"
        self.cloudclassname = "Cloud"
        self.cloudproc_crp = "proc_crp"
        self.cloudproc_alcohol = "proc_alcohol"
        self.output_crp = "crp_output"
        self.output_alcohol = "alcohol_output"
        self.configfilepath = Path(self.tempdir.name, "crate_test_nlp.ini")
        with open(self.configfilepath, "wt") as f:
            configtext = self._mk_nlp_config()
            log.debug(configtext)
            f.write(configtext)
        # import pdb; pdb.set_trace()

        # Server side
        register_all_crate_python_processors_with_serverprocessor()
        self.mock_pyramid_request = mock.Mock(name="mock_pyramid_request")
        self.server = NlpWebViews(request=self.mock_pyramid_request)
        self.server._authenticate = mock.Mock()
        self.server._set_body_json_from_request = mock.Mock(
            name="mock_set_body_json_from_request"
        )

        # Rather than modify the instances, let's try to modify the class. This
        # is because process_now() does its own instance creation.
        # (CloudRequest is the base class of CloudRequestProcess and
        # CloudRequestListProcessors.)
        CloudRequest._post_get_json = self._get_server_response

        # Client side #1
        self.mock_nlpdef = mock.Mock()
        self.mock_nlpdef.name = "testdef"
        self.listprocclient = CloudRequestListProcessors(
            nlpdef=self.mock_nlpdef
        )

        # Client side #2
        os.environ[NLP_CONFIG_ENV_VAR] = str(self.configfilepath.absolute())
        self.nlpdef = NlpDefinition(self.nlpdefname)  # loads the config
        self.crinfo = CloudRunInfo(nlpdef=self.nlpdef)

    def _mk_nlp_config(self) -> str:
        """
        Returns a test NLP config file.
        """
        return f"""
# NLP definitions

[{NlpConfigPrefixes.NLPDEF}:{self.nlpdefname}]
{NlpDefConfigKeys.INPUTFIELDDEFS} =
    {self.inputname}
{NlpDefConfigKeys.PROCESSORS} =
    {self.cloudclassname} {self.cloudproc_crp}
    {self.cloudclassname} {self.cloudproc_alcohol}
{NlpDefConfigKeys.PROGRESSDB} = {self.dbsectionname}
{NlpDefConfigKeys.HASHPHRASE} = blah
{NlpDefConfigKeys.CLOUD_CONFIG} = {self.cloudconfigname}
{NlpDefConfigKeys.CLOUD_REQUEST_DATA_DIR} = {self.tempdir.name}

# Inputs

[{NlpConfigPrefixes.INPUT}:{self.inputname}]
{InputFieldConfigKeys.SRCDB} = {self.dbsectionname}
{InputFieldConfigKeys.SRCTABLE} = {self.txttable}
{InputFieldConfigKeys.SRCPKFIELD} = {self.pkcol}
{InputFieldConfigKeys.SRCFIELD} = {self.txtcol}

# Processors

# - CRP
[{NlpConfigPrefixes.PROCESSOR}:{self.cloudproc_crp}]
{ProcessorConfigKeys.PROCESSOR_NAME} = crate_anon.nlp_manager.parse_biochemistry.Crp
{ProcessorConfigKeys.PROCESSOR_FORMAT} = {NlpDefValues.FORMAT_STANDARD}
{ProcessorConfigKeys.OUTPUTTYPEMAP} =
    crp {self.output_crp}
{ProcessorConfigKeys.DESTDB} = {self.dbsectionname}

# - Alcohol units
[{NlpConfigPrefixes.PROCESSOR}:{self.cloudproc_alcohol}]
{ProcessorConfigKeys.PROCESSOR_NAME} = crate_anon.nlp_manager.parse_substance_misuse.AlcoholUnits
{ProcessorConfigKeys.PROCESSOR_FORMAT} = {NlpDefValues.FORMAT_STANDARD}
{ProcessorConfigKeys.OUTPUTTYPEMAP} =
    AlcoholUnits {self.output_alcohol}
{ProcessorConfigKeys.DESTDB} = {self.dbsectionname}

# Output sections

# - CRP
[{NlpConfigPrefixes.OUTPUT}:{self.output_crp}]
{NlpOutputConfigKeys.DESTTABLE} = nlp_crp

# - Alcohol units
[{NlpConfigPrefixes.OUTPUT}:{self.output_alcohol}]
{NlpOutputConfigKeys.DESTTABLE} = nlp_alcohol

# Databases

[{NlpConfigPrefixes.DATABASE}:{self.dbsectionname}]
{DatabaseConfigKeys.URL} = {self.dburl}
{DatabaseConfigKeys.ECHO} = {self.echo}

# Cloud servers

[{NlpConfigPrefixes.CLOUD}:{self.cloudconfigname}]
{CloudNlpConfigKeys.CLOUD_URL} = https://dummy_url

"""  # noqa: E501

    def _mk_test_data(self) -> None:
        """
        Inserts some test data into a table.
        """
        texts = ["Current CRP 7. Teetotal. Non-smoker."]
        engine = create_engine(self.dburl)
        with engine.connect() as con:
            con.execute(
                f"""
                    CREATE TABLE {self.txttable} (
                        {self.pkcol} INTEGER,
                        {self.txtcol} TEXT
                    )
                """
            )
            for i, text in enumerate(texts, start=1):
                con.execute(
                    f"""
                        INSERT INTO {self.txttable}
                            ({self.pkcol}, {self.txtcol})
                            VALUES(:1, :2)
                    """,
                    i,
                    text,
                )

    # noinspection PyUnusedLocal
    def _get_server_response(
        self, request_json_str: str, may_fail: bool = None
    ) -> Dict[str, Any]:
        """
        Take a JSON request that has come from our mock client (in string
        form), and return a JSON response from our mock server (in dictionary
        form).
        """
        request_json = json.loads(request_json_str)
        log.debug(f"{request_json=}")
        self.server.body = request_json
        response_json = self.server.index()
        log.debug(f"-> {response_json=}")
        return response_json

    def test_get_remote_processor_columns(self) -> None:
        """
        Check that a client can request processor definitions from the server
        (testing both ends, just simplifying some communication between them,
        e.g. removing authentication). Check that the client can synthesise
        SQLAlchemy Column objects from the results.
        """
        # Fetch the data
        processors = self.listprocclient.get_remote_processors()
        # Check it
        self.assertIsInstance(processors, list)
        for sp in processors:
            self.assertIsInstance(sp, ServerProcessor)
            log.debug(f"+++ Trying {sp.name=}")

            # We won't go so far as to set up a mock database in full. But
            # check that Column object are created.
            # (a) setup
            c = Cloud(nlpdef=None, cfg_processor_name=None)
            c.procname = sp.name
            c._destdb = mock.Mock(name="mock_destdb")
            c._destdb.engine = self.dummy_engine
            c.set_procinfo_if_correct(sp)
            log.debug(f"--- {c.schema=}")
            for tablename in c.schema.keys():
                ouc = mock.Mock(name=f"mock_ouc_{tablename}")
                ouc.get_columns = lambda _engine: []
                ouc.renames = {}
                ouc.dest_tablename = tablename  # usually a property
                ouc.destfields = []
                # ... simulating OutputUserConfig
                c._outputtypemap[tablename] = ouc
                c._type_to_tablename[tablename] = tablename
            # (b) test
            self.assertTrue(c.is_tabular())
            table_columns = c.dest_tables_columns()
            self.assertTrue(len(table_columns) > 0)
            for tablename, columns in table_columns.items():
                log.debug(f"--- {sp.name=}: {tablename=}; {columns=}")
                self.assertTrue(len(columns) > 0)
                for col in columns:
                    self.assertIsInstance(col, Column)

    def test_cloud_pipeline(self) -> None:
        """
        Test the full pipeline:

        - create a source database (in setUp);
        - build a config file (in setUp);
        - create destination tables, based on remote processor definitions
          using tabular_schema;
        - run data through cloud NLP, and insert results.

        """
        drop_remake(nlpdef=self.nlpdef)
        process_cloud_now(crinfo=self.crinfo)
        # The test is (currently) that it doesn't crash.

        # To explore the database manually:
        # import pdb; pdb.set_trace()
