"""
crate_anon/testing/classes.py

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

Test classes for more complex tests e.g. where a database session is required.

"""

import logging
from typing import Generator, TYPE_CHECKING
from unittest import TestCase

from faker import Faker
import pytest
from sqlalchemy.engine.base import Engine

from crate_anon.testing.providers import register_all_providers
from crate_anon.testing.factories import (
    AnonTestBaseFactory,
    SecretBaseFactory,
    SourceTestBaseFactory,
    set_sqlalchemy_session_on_all_factories,
)

if TYPE_CHECKING:
    from sqlalchemy.orm.session import Session


class CrateTestCase(TestCase):
    def setUp(self) -> None:
        super().setUp()

        self.fake = Faker("en_GB")
        register_all_providers(self.fake)

    def assert_logged(
        self,
        logger_name: str,
        level: int,
        expected_message: str,
        logging_cm: Generator[None, None, None],
    ) -> None:
        level_name = logging.getLevelName(level)
        search = f"{level_name}:{logger_name}:{expected_message}"

        self.assertTrue(
            any(search in line for line in logging_cm.output),
            msg=f"Failed to find '{search}' in {logging_cm.output}",
        )


class CommonDatabaseTestCase(CrateTestCase):
    """
    Base class for testing with a database. Do not inherit from this directly,
    use one of the below subclasses instead, which will be associated with
    pytest fixtures for engine, session etc.
    """

    anon_dbsession: "Session"
    secret_dbsession: "Session"
    source_dbsession: "Session"
    anon_engine: Engine
    secret_engine: Engine
    source_engine: Engine
    databases_on_disk: bool
    anon_db_filename: str
    secret_db_filename: str
    source_db_filename: str

    def setUp(self) -> None:
        set_sqlalchemy_session_on_all_factories(
            AnonTestBaseFactory, self.anon_dbsession
        )
        set_sqlalchemy_session_on_all_factories(
            SecretBaseFactory, self.secret_dbsession
        )
        set_sqlalchemy_session_on_all_factories(
            SourceTestBaseFactory, self.source_dbsession
        )

    def set_echo(self, echo: bool) -> None:
        """
        Changes the database echo status.
        """
        self.anon_engine.echo = echo
        self.secret_engine.echo = echo
        self.source_engine.echo = echo


@pytest.mark.usefixtures("setup")
class DatabaseTestCase(CommonDatabaseTestCase):
    """
    Base class for testing with a database.

    The pytest fixtures defined in conftest.py run each test in a transaction,
    rolling back the transaction at the end of the test. This all works fine,
    unless one of the tests encounters a DatabaseError and the transaction
    needs to be rolled back. In this case we need the approach taken by
    SlowSecretDatabaseTestCase below.
    """


@pytest.mark.usefixtures("slow_secret_setup")
class SlowSecretDatabaseTestCase(CommonDatabaseTestCase):
    """
    Like DatabaseTestCase but we create and drop all of the tables for the
    secret database every time a test is run. Potentially slow if there are
    lots of tables.
    """


class DemoDatabaseTestCase(DatabaseTestCase):
    """
    Base class for use with test factories such as
    DemoPatientFactory
    """
