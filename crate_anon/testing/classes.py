#!/usr/bin/env python

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

from cardinal_pythonlib.classes import all_subclasses
import pytest
from sqlalchemy import MetaData
from sqlalchemy.engine.base import Engine
from sqlalchemy.orm import declarative_base

from crate_anon.testing.factories import BaseFactory

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

metadata = MetaData()
Base = declarative_base(metadata=metadata)


@pytest.mark.usefixtures("setup")
class DatabaseTestCase(TestCase):
    dbsession: "Session"
    engine: Engine
    database_on_disk: bool
    db_filename: str

    def setUp(self) -> None:
        for factory in all_subclasses(BaseFactory):
            factory._meta.sqlalchemy_session = self.dbsession

    def set_echo(self, echo: bool) -> None:
        """
        Changes the database echo status.
        """
        self.engine.echo = echo