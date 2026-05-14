"""
crate_anon/crateweb/research/tests/research_db_info_tests.py

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

Test research_db_info.py.

"""

# =============================================================================
# Imports
# =============================================================================

import logging
import os.path
from tempfile import TemporaryDirectory

from cardinal_pythonlib.dbfunc import dictfetchall
from cardinal_pythonlib.sql.sql_grammar import SqlGrammar
from django.test.testcases import TestCase  # inherits from unittest.TestCase

from crate_anon.crateweb.config.constants import ResearchDbInfoKeys as RDIKeys
from crate_anon.crateweb.core.constants import (
    DJANGO_DEFAULT_CONNECTION,
    RESEARCH_DB_CONNECTION_NAME,
)
from crate_anon.crateweb.raw_sql.database_connection import DatabaseConnection
from crate_anon.crateweb.research.research_db_info import (
    SingleResearchDatabase,
    ResearchDatabaseInfo,
)

log = logging.getLogger(__name__)


# =============================================================================
# Unit tests
# =============================================================================


class ResearchDBInfoTests(TestCase):
    databases = {DJANGO_DEFAULT_CONNECTION, RESEARCH_DB_CONNECTION_NAME}
    # ... or the test framework will produce this:
    #
    # django.test.testcases.DatabaseOperationForbidden: Database queries to
    # 'research' are not allowed in this test. Add 'research' to
    # research_db_info_tests.ResearchDBInfoTests.databases to ensure proper
    # test isolation and silence this failure.
    #
    # It is checked by a classmethod, not an instance.

    def setUp(self):
        super().setUp()

        # crate_anon.common.constants.RUNNING_WITHOUT_CONFIG = True

        # If we have two SQLite in-memory database (with name = ":memory:"),
        # they appear to be the same database. But equally, if you use a local
        # temporary directory, nothing is created on disk; so presumably the
        # Django test framework is intercepting everything?
        self.tempdir = TemporaryDirectory()  # will be deleted on destruction
        self.settings(
            DATABASES={
                DJANGO_DEFAULT_CONNECTION: {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": os.path.join(self.tempdir.name, "main.sqlite3"),
                },
                RESEARCH_DB_CONNECTION_NAME: {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": os.path.join(
                        self.tempdir.name, "research.sqlite3"
                    ),
                },
            },
            # DEBUG=True,
            RESEARCH_DB_INFO=[
                {
                    RDIKeys.NAME: "research",
                    RDIKeys.DESCRIPTION: "Demo research database",
                    RDIKeys.DATABASE: "",
                    RDIKeys.SCHEMA: "research",
                    RDIKeys.PID_PSEUDO_FIELD: "pid",
                    RDIKeys.MPID_PSEUDO_FIELD: "mpid",
                    RDIKeys.TRID_FIELD: "trid",
                    RDIKeys.RID_FIELD: "brcid",
                    RDIKeys.RID_FAMILY: 1,
                    RDIKeys.MRID_TABLE: "patients",
                    RDIKeys.MRID_FIELD: "nhshash",
                    RDIKeys.PID_DESCRIPTION: "Patient ID",
                    RDIKeys.MPID_DESCRIPTION: "Master patient ID",
                    RDIKeys.RID_DESCRIPTION: "Research ID",
                    RDIKeys.MRID_DESCRIPTION: "Master research ID",
                    RDIKeys.TRID_DESCRIPTION: "Transient research ID",
                    RDIKeys.SECRET_LOOKUP_DB: "secret",
                    RDIKeys.DATE_FIELDS_BY_TABLE: {},
                    RDIKeys.DEFAULT_DATE_FIELDS: [],
                    RDIKeys.UPDATE_DATE_FIELD: "_when_fetched_utc",
                },
            ],
        )
        self.resconn = DatabaseConnection(RESEARCH_DB_CONNECTION_NAME)
        self.grammar = SqlGrammar()
        with self.resconn.connection.cursor() as cursor:
            cursor.execute("CREATE TABLE t (a INT, b INT)")
            cursor.execute("INSERT INTO t (a, b) VALUES (1, 101)")
            cursor.execute("INSERT INTO t (a, b) VALUES (2, 102)")
            cursor.execute("COMMIT")

    def tearDown(self) -> None:
        with self.resconn.connection.cursor() as cursor:
            cursor.execute("DROP TABLE t")
        # Otherwise, you can run one test, but if you run two, you get:
        #
        # django.db.transaction.TransactionManagementError: An error occurred
        # in the current transaction. You can't execute queries until the end
        # of the 'atomic' block.
        #
        # ... no - still the problem!
        # Hack: combine the tests.

    def test_django_dummy_database_and_sqlite_schema_reader(self) -> None:
        with self.resconn.connection.cursor() as cursor:
            cursor.execute("SELECT * FROM t")
            results = dictfetchall(cursor)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], dict(a=1, b=101))
        self.assertEqual(results[1], dict(a=2, b=102))

        rdbi = ResearchDatabaseInfo(running_without_config=True)
        srd = SingleResearchDatabase(
            index=0,
            grammar=self.grammar,
            rdb_info=rdbi,
            connection=self.resconn,
        )
        col_info_list = srd.schema_infodictlist  # will read the database
        # Unfortunately it will read all the Django tables too (see above).
        table_t_cols = [c for c in col_info_list if c["table_name"] == "t"]
        self.assertTrue(len(table_t_cols) == 2)
        row0 = table_t_cols[0]
        self.assertEqual(row0["column_name"], "a")
        self.assertEqual(row0["column_type"], "INT")
        row1 = table_t_cols[1]
        self.assertEqual(row1["column_name"], "b")
        self.assertEqual(row1["column_type"], "INT")
