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

from typing import TYPE_CHECKING
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
    from sqlalchemy.orm import Session


@pytest.mark.usefixtures("setup")
class DatabaseTestCase(TestCase):
    """
    Base class for testing with a database.
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


class DemoDatabaseTestCase(DatabaseTestCase):
    """
    Base class for use with test factories such as
    DemoPatientFactory
    """

    def setUp(self) -> None:
        super().setUp()

        self.fake = Faker("en_GB")
        register_all_providers(self.fake)
